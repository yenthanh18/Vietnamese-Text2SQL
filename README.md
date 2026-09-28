# Vietnamese Text-to-SQL — Web skeleton và kiến trúc NLP runtime

Ứng dụng gồm React/Vite, FastAPI, PostgreSQL và Spider SQLite. `/api/query` đã nối
luồng E2/E3 → mapping → SELECT-only execution, nhưng không tự load model.
Các artifact nghiên cứu và NLP pipeline được giữ nguyên. ViText2SQL là dataset
training/evaluation; `student_management_demo` là database ứng dụng demo.

## Yêu cầu

- Python 3.10 trở lên.
- Node.js 22.12 trở lên (hoặc Node.js 20.19 trở lên).
- PostgreSQL đã có database `student_management_demo` và dữ liệu hiện tại.

## Cài đặt trên Windows PowerShell

Chạy từ project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-web.txt
Copy-Item .env.example .env
```

Nếu đã có `.env`, giữ file đó, không chạy lại lệnh copy. Mở `.env` bằng editor và
điền cấu hình local của bạn:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=student_management_demo
DB_USER=postgres
DB_PASSWORD=
MODEL_DEVICE=cpu
BASE_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct
ADAPTER_PATH=model/e2_qlora_dew_final
```

Điền mật khẩu thật vào `DB_PASSWORD` trên máy của bạn; không commit hay gửi mật khẩu.
Nếu mật khẩu có ký tự `#` hoặc khoảng trắng, đặt giá trị trong dấu nháy.
Backend đọc `.env` ở project root bất kể working directory; biến môi trường của
process có độ ưu tiên cao hơn `.env`. Khởi động lại backend sau khi đổi cấu hình.
Không chạy lại `database/schema.sql` hoặc `database/seed.sql`.

Cài frontend:

```powershell
cd frontend
npm.cmd ci
cd ..
```

## Chạy ứng dụng

Terminal 1, từ project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, từ project root:

```powershell
cd frontend
npm.cmd run dev
```

Không cần activate virtual environment hoặc thay đổi PowerShell execution policy.

| Trang/API | URL |
| --- | --- |
| Backend | http://127.0.0.1:8000/ |
| Health | http://127.0.0.1:8000/health |
| Schema | http://127.0.0.1:8000/schema |
| NLP status | http://127.0.0.1:8000/nlp/status |
| Swagger UI | http://127.0.0.1:8000/docs |
| Frontend | http://127.0.0.1:5173/ |

Frontend gọi trực tiếp FastAPI tại `http://127.0.0.1:8000`.
CORS chỉ cho phép `http://localhost:5173` và `http://127.0.0.1:5173`,
với GET/POST và Content-Type. Vite không tự đổi cổng nếu 5173 bị chiếm.

## API

- `GET /`: backend đang hoạt động, không cần kết nối database.
- `GET /health`: chạy `SELECT 1`; HTTP 200 nếu kết nối được, HTTP 503 nếu thất bại.
- `GET /schema`: introspect tất cả bảng trong schema `public`, trả tên bảng,
  cột, kiểu dữ liệu, nullable, primary keys và foreign keys; HTTP 503 nếu không đọc được.
- `GET /nlp/status`: đọc metadata/artifacts, trả trạng thái model, device, base model,
  đường dẫn adapter, số schema và DEW availability; không tải model hoặc import PyTorch.
- `POST /api/query`: nhận `question` từ 1–2000 ký tự sau khi bỏ khoảng trắng hai đầu
  và `db_id` trong ViText2SQL. Request ví dụ:

```json
{
  "question": "Có bao nhiêu bộ phim?",
  "db_id": "cinema"
}
```

Khi chưa tải model, trả HTTP 503 với `detail`: `Model chưa tải. NLP inference hiện
không khả dụng.` Không có SQL giả/placeholder. Request rỗng/sai định dạng trả 422;
db_id không tồn tại trả 404, được kiểm tra trước trạng thái model.

SQLAlchemy tạo kết nối lazily, timeout kết nối 5 giây, statement timeout 5 giây
và transaction mặc định read-only. Không có ORM model, migration hoặc API ghi dữ liệu.
Lỗi kết nối không trả credentials hay nội dung exception cho frontend.

## Kiểm tra

Từ project root:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend
cd frontend
npm.cmd run build
cd ..
```

Kiểm tra thủ công sau khi chạy hai server:

1. `/` trả `status: ok`.
2. Cấu hình `.env` đúng: `/health` trả `postgresql: connected`, `/schema` hiển thị
   năm bảng hiện có cùng columns, primary keys và foreign keys.
3. Frontend tải danh sách ViText2SQL từ `/api/databases`, mặc định chọn `cinema`.
   Tìm db_id, chọn `college_2` hoặc `academic`; danh sách bảng/cột cập nhật theo database.
4. Mở tên bảng để xem cột tiếng Việt và primary key; danh sách schema dài có thể cuộn.
5. Database mục tiêu hiển thị cạnh trạng thái model từ `/nlp/status`. Nút Truy vấn
   bị khóa khi model chưa tải; ba vùng kết quả giữ trạng thái trống trung lập.
6. Nút Tải lại metadata cập nhật trạng thái model. Khi model sẵn sàng, UI gửi
   question + db_id tới `/api/query`, hiển thị generated_sql và columns/rows.
   Câu trả lời tiếng Việt vẫn trống. UI không gọi endpoint development `/execute`;
   PostgreSQL vẫn được kiểm tra riêng qua `/health` và `/schema`.

## Dependencies

Backend: FastAPI, Uvicorn, SQLAlchemy, Psycopg 3 binary, pydantic-settings, SQLGlot.
`backend/requirements-web.txt` dành cho máy chạy Web không inference.
`backend/requirements.txt` bao gồm Web và torch, transformers, peft, accelerate
cho môi trường inference sau này. Không cần cài lại dependencies trên máy hiện tại
chỉ để sử dụng `/nlp/status`.
Frontend runtime: React, React DOM. Build/dev: Vite. Styling dùng CSS thuần.
`frontend/package-lock.json` khóa phiên bản frontend cho `npm ci`.

## Cấu trúc mới

```text
.env.example
.gitignore
README.md
backend/
  __init__.py
  main.py
  config.py
  database.py
  requirements.txt
  requirements-web.txt
  routers/
    __init__.py
    status.py
    query.py
    nlp.py
  services/
    __init__.py
    schema.py
    model_runtime.py
    text2sql.py
frontend/
  package.json
  package-lock.json
  vite.config.js
  index.html
  src/
    main.jsx
    App.jsx
    api.js
    styles.css
```

## Chuẩn bị runtime NLP (chưa bật inference)

Training đã hoàn tất. Khi được gọi tường minh trong môi trường inference,
`ModelRuntime.load_model()` tải base model `Qwen/Qwen2.5-Coder-3B-Instruct`,
tokenizer/chat template đã lưu và QLoRA adapter tại `model/e2_qlora_dew_final/`.
`adapter_model.safetensors` chứa trọng số adapter đã huấn luyện, không phải toàn bộ
Qwen; base model vẫn bắt buộc tại thời điểm inference. Không retrain hoặc sửa artifacts.

FastAPI không gọi `load_model()` khi khởi động hay xử lý HTTP. Không có endpoint tải
model. `/api/query` chỉ chạy inference nếu runtime đã được tải tường minh trước đó.
Máy Windows CPU-only chạy Web, `/health`, `/schema`, `/nlp/status` mà không cần model
hoặc thư viện inference. `MODEL_DEVICE` mặc định `cpu`, hỗ trợ `cuda` và `cuda:N`;
`ADAPTER_PATH` tương đối được tính từ project root. Giữ nguyên `.env` và mật khẩu
database hiện có; chỉ thêm các biến MODEL_DEVICE/BASE_MODEL/ADAPTER_PATH nếu cần.

`Text2SQLService` đọc tables.json và DEW dictionary khi khởi tạo. Các giá trị
`tables_data`, `vt_map`, `SYSTEM_PROMPT` được chuẩn bị từ artifacts; việc gán chúng
vào `nlp.pipeline` được trì hoãn đến lúc generate vì module nghiên cứu import torch
ngay đầu file. `pipeline.tokenizer/model_e2` chỉ được gán sau khi runtime đã tải model.
System prompt giống nguyên văn notebook. Gọi generate trước khi tải model sẽ nhận
`ModelNotLoadedError`, không kích hoạt download.

Service gọi lại đúng các hàm nghiên cứu: DEW tagging → E2 greedy → đếm vi phạm;
nếu có vi phạm thì gọi E3 với 5 beams/5 return sequences và `select_e3_candidate()`.
Sample E2/E3 dùng câu hỏi đã gắn DEW tags. Metadata trả raw/tagged question, db_id,
E2 SQL, số vi phạm E2, cờ E3 và final SQL. Router ánh xạ final SQL rồi chuyển cho
lớp Spider chỉ đọc. E3 không chạy nếu số vi phạm E2 bằng 0.

166 schema trong dataset là schema nghiên cứu, không tự ánh xạ sang PostgreSQL
demo. `db_id` phải tồn tại trong cả tables.json và DEW dictionary. Schema adapter
cho `student_management_demo` và trả lời ngôn ngữ tự nhiên
vẫn là công việc sau này.

GPU được khuyến nghị cho E2/E3 thực tế. CPU dùng float32; CUDA dùng float16 mặc định.
Chỉ khi gọi tường minh `load_model(use_4bit=True)` trên CUDA mới cần cài thêm
`bitsandbytes` tương thích với GPU/PyTorch. Không cần bitsandbytes cho CPU startup.
Tham khảo [PEFT loading](https://huggingface.co/docs/peft/main/package_reference/peft_model)
và [Transformers 4-bit](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes).
Lệnh cài dành cho môi trường inference tương lai (không cần chạy trên máy demo):

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
# Chỉ dành cho CUDA 4-bit:
.\.venv\Scripts\python.exe -m pip install bitsandbytes
```

Các phiên bản dependencies inference và quá trình tải/inference chưa được kiểm tra
trên GPU trong giai đoạn này. Không tải base model hoặc chạy inference để kiểm tra Web.

## Spider SQLite: metadata và thực thi chỉ đọc

`db_id` liên kết tables.json, DEW dictionary và
`database/spider/<db_id>/<db_id>.sqlite`. Hiện có 166 database. Metadata API chỉ đọc
tables.json, không quét dữ liệu SQLite. Các endpoint PostgreSQL và `/nlp/status`
giữ nguyên; `/api/query` sử dụng cùng lớp thực thi SQLite chỉ đọc sau mapping.

Cấu hình tùy chọn (thêm vào `.env` hiện có nếu cần, giữ nguyên mật khẩu):

```dotenv
SPIDER_DB_PATH=database/spider
SPIDER_EXECUTE_ENABLED=true
```

Đường dẫn tương đối tính từ project root. Endpoint execute dành riêng cho local
development/testing; đặt `SPIDER_EXECUTE_ENABLED=false` khi triển khai. Tiếp tục
bind server vào `127.0.0.1`; endpoint này chưa có xác thực người dùng.

- `GET /api/databases`: JSON array gồm db_id, table_count, table_names của 166 schema.
- `GET /api/databases/{db_id}/schema`: db_id, tables, columns, primary_keys và
  foreign_keys; tên tiếng Việt giữ nguyên từ tables.json. Column/table IDs theo
  dataset, gồm wildcard có table_id=-1.
- `POST /api/databases/{db_id}/execute`: body `{"sql":"SELECT ..."}`;
  trả columns, rows, row_count và truncated. row_count là số dòng đã trả (tối đa
  100), không phải tổng số dòng của truy vấn; truncated báo còn dòng khác.

Chỉ nhận một statement bắt đầu bằng SELECT; chưa hỗ trợ WITH hoặc comment đầu
câu. SQLite authorizer chặn thao tác ngoài đọc và function ngoài allowlist;
load_extension, PRAGMA, ATTACH, các lệnh ghi/admin và nhiều statement bị từ chối.
Kết nối dùng URI mode=ro, query_only, đóng sau mỗi truy vấn; không tạo file thiếu.
Truy vấn bị ngắt sau khoảng 2 giây bởi progress handler. Kết quả BLOB được biểu diễn
dưới dạng `{"hex":"..."}`. Lỗi đầu vào/SQL trả 400 (validation body trả 422),
db_id/file không tồn tại trả 404, timeout trả 408, execute bị tắt trả 403.

Tên tiếng Việt trong metadata có thể khác tên vật lý tiếng Anh trong SQLite.
Endpoint này thực thi SQL theo tên vật lý, chưa dịch identifier hoặc kiểm chứng
SQL từ model. Không nên giả định SQL sinh theo schema tiếng Việt sẽ chạy trực tiếp.

Ví dụ kiểm thử thủ công (SQL do người dùng cung cấp, không phải output model):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/databases
Invoke-RestMethod http://127.0.0.1:8000/api/databases/academic/schema
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/databases/academic/execute -ContentType 'application/json' -Body '{"sql":"SELECT count(*) FROM author"}'
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Các file bổ sung: `backend/services/spider_database.py`,
`backend/routers/databases.py`, `backend/tests/test_spider_database.py`.
SQLite sử dụng thư viện chuẩn Python; không cần cài dependency mới.

## Mapping và orchestration `/api/query`

`backend/services/schema_mapper.py` dùng đúng nguyên tắc index của evaluation:
bảng theo `sqlite_master ORDER BY rowid`, cột theo `PRAGMA table_info` trong từng
bảng; introspection mở database với `mode=ro`. Số bảng/cột phải khớp metadata.
Không có bảng dịch thủ công cho 166 database.

Mapper nhận SQL theo schema ViText2SQL. Các cụm tên nhiều từ không có quote được
quote theo schema, bỏ qua string/comment/identifier đã quote. Sau đó SQLGlot phân
tích AST và scope để đổi tên bảng/cột. Hỗ trợ alias, qualified columns, JOIN ON,
aggregate, scalar/EXISTS correlated subquery; derived table yêu cầu AS rõ ràng
cho từng cột đầu ra. Literal dùng nháy đơn giữ nguyên giá trị; nháy kép/backtick/
ngoặc vuông được hiểu là identifier, không đoán thành string khi không tìm thấy.
Alias đầu ra ORDER/GROUP/HAVING chỉ được giữ khi không mơ hồ với cột nguồn.
Tham khảo [SQLGlot scope](https://github.com/tobymao/sqlglot/blob/main/sqlglot/optimizer/scope.py).

Mapping trả HTTP 422 khi thiếu/không rõ identifier, tên tiếng Việt trùng nhiều
cột vật lý, schema không khớp, hoặc cấu trúc chưa hỗ trợ. Ví dụ `academic` có hai
cột tên `số lượng trích dẫn` trong `bài báo`; tham chiếu tên đó bị từ chối. Các cột
khác vẫn ánh xạ được. WITH, set operations (UNION/INTERSECT/EXCEPT), JOIN USING/
NATURAL, alias có danh sách đổi tên cột và nhiều statement hiện bị từ chối.
Mapping theo index phụ thuộc thứ tự schema như evaluation; nếu database được
thay thế/reorder cùng số cột, index không chứng minh được sự tương ứng về ngữ nghĩa.
Kiểm tra metadata hiện tại: 165/166 database xây được mapping;
`cre_Drama_Workshop_Groups` bị từ chối vì tên bảng tiếng Việt trùng lặp.

Response thành công gồm question, db_id, tagged_question, e2_sql, e3_triggered,
schema_violations (của E2), generated_sql (final SQL model), execution_sql (SQL đã
map thực sự chạy), columns, rows, row_count, truncated. Không có câu trả lời ngôn
ngữ tự nhiên trong phase này. Giới hạn 100 dòng và SQLite authorizer được giữ nguyên.
`SPIDER_EXECUTE_ENABLED` chỉ điều khiển endpoint SQL thủ công dành cho development,
không điều khiển orchestration model. Lỗi inference bất ngờ trả HTTP 500 có thông
báo chung; lỗi SELECT giữ status của lớp Spider hiện có.

Frontend giữ question và db_id, có loading/error, xóa kết quả khi đổi database
và bỏ qua phản hồi cũ. Timeout client cho inference là 120 giây; hết timeout ở
client không tự hủy phép tính đang chạy trên server.

Kiểm thử không tải model:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

`test_query.py` kiểm tra mapping trên cinema/academic/college_2, nested queries,
literals, lỗi mơ hồ, validation và model-unavailable. Orchestration/E3 dùng test
doubles chỉ bên trong automated tests; ứng dụng không có chế độ fake inference.
Không cần torch/transformers hoặc Qwen weights để chạy các kiểm thử này.
