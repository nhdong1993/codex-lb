# Lỗi compaction của model từ Model Source

## Mục tiêu bàn giao

Sửa lỗi Codex gọi model từ Model Source thành công ở các lượt thường nhưng bị
`Compaction interrupted` khi nén lịch sử. Tài liệu này ghi lại chẩn đoán đã xác
minh ngày **2026-10-07 UTC** để agent tiếp theo có thể thực hiện bản sửa.

**Trạng thái cập nhật 2026-10-07:** đã triển khai bản sửa và regression test ở
local; xem [verification.md](verification.md) để biết phạm vi xác minh. Chưa
deploy hoặc đổi cấu hình dịch vụ. Phần chẩn đoán bên dưới giữ lại bằng chứng
trước bản sửa. Key tạm dùng chẩn đoán đã được xóa; tài liệu không chứa credential
hay nội dung hội thoại thật.

Đã bổ sung `proposal.md`, `design.md`, `tasks.md` và delta specs trước khi sửa
hành vi theo quy trình OpenSpec. Yêu cầu normative nằm trong spec; bằng chứng
và lý do nằm trong context.

## Triệu chứng và nguyên nhân đã xác minh

Model public: `ch-relay/gpt-6-astra`.

Model Source: `ch-relay (VPS)`, base URL lúc kiểm tra:
`http://172.31.245.1:11500/v1`.

Metadata ánh xạ model: `upstream_model: gpt-6-astra`.
Nguồn đã bật và hỗ trợ HTTP Responses. Gọi Responses thường qua codex-lb đi đúng
nguồn, trả HTTP 200. Khi Codex compact, người dùng nhận:

```text
Compaction interrupted
The 'ch-relay/gpt-6-astra' model is not supported when using Codex with a ChatGPT account.
```

Request log production ID **779364**, lúc **2026-10-07 03:03:30 UTC**, ghi nhận:

- `request_kind = compaction`, transport HTTP.
- `model_source_id = null`, có `account_id`: request đi sang subscription account.
- Upstream HTTP 400 với thông báo trên.
- Lượt thường ngay trước đó, log ID **779357**, đi đúng Model Source và thành công.

Nhánh compact của codex-lb tại thời điểm chẩn đoán dùng đường subscription account, bỏ qua việc
chọn Model Source và ánh xạ public model. Do đó upstream ChatGPT nhận nguyên tên
`ch-relay/gpt-6-astra` và từ chối. Đây là lỗi ở đường compaction của codex-lb;
việc chỉnh source assignment cho lượt thường không giải quyết được nhánh này.

## Kết quả gọi thử thực tế

Kiểm tra qua ingress HA `http://127.0.0.1:2455`, bằng key tạm được cấp qua
`ApiKeysService`, giới hạn model public và source nói trên. Không lấy hoặc đổi
key đang dùng của operator.

| Đích | Đường gọi | Payload | Kết quả |
| --- | --- | --- | --- |
| ch-relay native, cổng 11502 | `/v1/responses/compact` | Lịch sử ngắn, model upstream | HTTP 404 |
| ch-relay native, cổng 11502 | `/v1/responses` | Có terminal `compaction_trigger` | HTTP 200, `response.completed`, output `compaction` có `encrypted_content`; usage 376 → 272 |
| codex-lb | `/v1/responses` | Lượt thường, model public | HTTP 200, đi đúng source |
| codex-lb | `/v1/responses/compact` | Lịch sử ngắn, model public | HTTP 400, đi sang account, tái hiện đúng lỗi unsupported model |
| codex-lb | `/backend-api/codex/responses` | Có terminal `compaction_trigger`, model public | HTTP 400, đi sang account, tái hiện đúng lỗi unsupported model |
| codex-lb | `/v1/responses` | Có terminal `compaction_trigger`, model public | HTTP 200, đi đúng source, output `compaction` mã hóa; usage 376 → 303 |

Log kiểm thử codex-lb: **779730** (lượt thường thành công), **779736** (compact
endpoint lỗi), **779742** (Codex trigger lỗi), **779755** (v1 trigger thành công).

Kết quả 404 chỉ xác nhận hành vi của endpoint/upstream đã thử tại thời điểm đó;
không suy ra mọi provider đều thiếu `/responses/compact`. Tool có route compact
trong binary nhưng route gọi thực tế này vẫn trả 404. Đường trigger đã được
kiểm chứng thành công, nên không chỉ chuyển request sang endpoint compact của
tool và coi như đã sửa xong.

## Payload tái hiện không chứa dữ liệu thật

Body cho `/v1/responses/compact`:

```json
{
  "model": "ch-relay/gpt-6-astra",
  "instructions": "Summarize the conversation so work can continue.",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "We are testing a small Python function that adds two numbers."
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Use def add(a, b): return a + b."
        }
      ]
    }
  ]
}
```

Để thử trigger, dùng cùng body, thêm `{"type":"compaction_trigger"}` làm phần
tử cuối duy nhất trong `input`, thêm `"stream": true`, `"store": false`, rồi
POST lần lượt đến `/backend-api/codex/responses` và `/v1/responses` của codex-lb.
Khi gọi trực tiếp ch-relay native, thay model bằng `gpt-6-astra`.

Đọc SSE đến terminal event, kiểm tra `response.completed` và output type
`compaction` có `encrypted_content`; HTTP 200 một mình chưa đủ chứng minh
compaction thành công. Không in nội dung mã hóa hoặc secret ra log. Usage cụ thể
có thể thay đổi giữa các lần thử.

## Vị trí code và spec cần đọc

- `app/modules/proxy/api.py`:
  - `responses_compact`, `v1_responses_compact`, `_compact_responses`: nhánh compact
    chuyên biệt có comment xác nhận đường hiện tại là subscription-only.
  - Handler Codex HTTP Responses: `responses_source_route_excluded(...)` đang
    loại terminal compaction khỏi source routing.
  - `v1_responses`: dùng `exclude_compaction=False`, nên v1 trigger đã đi đúng
    nguồn trong kiểm thử.
  - Nhánh `compact_payload` trong `_stream_responses`: chuyển trigger sang
    `context.service.compact_responses` ở đường subscription.
  - `_normalize_codex_remote_compaction_v2_result` và các helper synthetic
    compaction: đọc trước khi chuyển đổi hình dạng response.
- `app/modules/proxy/request_policy.py`:
  `responses_source_route_excluded`, `strip_terminal_compaction_trigger_input`,
  validator cho terminal compaction trigger.
- `app/modules/proxy/_service/compact.py`: account selection, continuity,
  usage reservation/settlement và retry của compact hiện tại.
- `app/modules/model_sources/selection.py`, `forwarding.py`, `aliases.py`,
  `projection.py`, `ownership_repository.py`: tái sử dụng chính sách nguồn,
  alias, giới hạn và ownership có sẵn.
- `app/core/clients/proxy.py`: compact subscription đang chuyển request thành
  Responses streaming với terminal trigger; tham khảo contract, không tái sử
  dụng credential/selection của subscription cho source.
- `tests/integration/test_proxy_compact.py`, `test_proxy_compact_triggers.py`,
  `compact_test_helpers.py` và các integration test Model Source hiện có.
- Spec hiện có:
  [model-source-routing](../../../specs/model-source-routing/spec.md),
  [context routing](../../../specs/model-source-routing/context.md),
  [responses-api-compat](../../../specs/responses-api-compat/spec.md),
  [model-source-websocket](../../../specs/model-source-websocket/spec.md).

Context routing hiện mô tả feature không bổ sung compaction; khi sửa cần cập
nhật contract này thay vì chỉ bỏ guard trong code.

## Hướng sửa và tiêu chí hoàn thành

1. Chọn nguồn cho source-owned compaction bằng cùng chính sách public/enforced
   model, source assignment, enablement và continuity của Responses thường.
   Không gửi public source alias sang subscription account khi nguồn sở hữu
   request đó. Subscription-owned compact vẫn giữ contract hiện có.
2. Với upstream đã kiểm chứng ở đây, chuyển compact sang HTTP Responses có
   terminal `compaction_trigger`, đúng upstream model `gpt-6-astra`, rồi trả
   đúng contract JSON compact hoặc SSE Codex tương ứng đường vào. Cách lựa
   chọn compact endpoint/trigger cho các provider khác cần được thiết kế trong
   proposal; không hardcode tên `ch-relay` để bỏ qua policy chung.
3. Giữ đúng owner của encrypted reasoning, compaction và response/call reference;
   không chuyển state sang credential khác. Disabled source, owner bị đổi
   credential, conflicting/unknown ownership trong pool và file pin phải được
   xử lý theo contract hiện hành, không fallback ngầm sang account.
4. Giữ input hợp lệ và public model identity; không bỏ lịch sử, thay compaction
   mã hóa bằng summary text giả hoặc chỉ strip prefix để gọi account khác.
5. Ghi request log là compaction với source/revision thực tế. Capture usage,
   cached/reasoning tokens theo mức upstream hỗ trợ, settle reservation đúng
   một lần, bảo đảm cleanup khi lỗi/cancel/timeout và không retry sau khi đã
   trả kết quả có state cho client.
6. Có regression test tại API path thực sự lỗi, cho `/v1/responses/compact`,
   đường Codex compact endpoint và terminal trigger trên Codex Responses,
   gồm trailing slash theo contract repository. Kiểm tra v1 trigger hiện
   đang chạy vẫn thành công; subscription compact không bị hồi quy.
7. Kiểm tra continuation dùng output compact trên cùng source, gồm request tiếp
   theo vào HA replica khác; ownership phải được ghi nhận để lần gọi tiếp theo
   không bị 409 hoặc chọn sai credential. Kiểm thử negative cases và cleanup
   cần thiết, không chỉ happy path.

## Kiểm chứng và triển khai

Agent sửa cần validate OpenSpec, chạy các integration/unit check phù hợp và ghi
rõ bản sửa mới ở local hay đã deploy. Đọc quy tắc HA trong `AGENTS.md`: nếu có
yêu cầu triển khai, dùng `scripts/deploy-compose-ha.sh deploy`, không recreate
trực tiếp blue/green/amber. Repo có nhiều thay đổi sẵn từ công việc khác; giữ
nguyên các thay đổi đó và cô lập phạm vi bản sửa này.

Cảnh báo riêng tại thời điểm chẩn đoán: vendor có log `license suspended` và
`policyLoaded=false`, mặc dù các cuộc gọi HTTP kiểm thử trên vẫn thành công.
Nếu live test sau này thất bại, phân biệt tình trạng license/upstream mới với
lỗi routing đã tái hiện; không thay license hay cơ chế kiểm tra license để
khắc phục lỗi compact.

Bằng chứng JSON gốc đã lọc secret nằm trên VPS tại
`/home/dong01/ch-relay-docker/compaction-validation.json`. Tài liệu này đã chứa
các kết quả cần thiết, không cần đọc file credential để bắt đầu sửa.
