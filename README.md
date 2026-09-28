# Vietnamese Text-to-SQL System

Hệ thống chuyển đổi câu hỏi ngôn ngữ tự nhiên tiếng Việt thành câu lệnh SQL và thực thi trực tiếp trên cơ sở dữ liệu.

Đồ án được xây dựng cho bài toán **Vietnamese Text-to-SQL**, sử dụng **Qwen2.5-Coder-3B-Instruct**, tinh chỉnh bằng **QLoRA**, kết hợp cơ chế **DEW** hỗ trợ liên kết lược đồ (Schema linking) và **giải mã ứng viên có ràng buộc lược đồ E3 (Schema-aware constrained candidate decoding)**.

Ứng dụng Web được triển khai với **React + FastAPI**, cho phép người dùng lựa chọn cơ sở dữ liệu, nhập câu hỏi bằng tiếng Việt, sinh SQL, thực thi truy vấn và xem kết quả trực tiếp.

---

## 1. Kiến trúc hệ thống

Pipeline chính của hệ thống:

```text
Vietnamese Question
        ↓
Database Schema
        ↓
DEW Schema Tagging
        ↓
Qwen2.5-Coder-3B-Instruct + QLoRA
        ↓
E2 Greedy SQL Generation
        ↓
Schema Violation Detection
        ↓
E3 Schema-aware Constrained Candidate Decoding
        ↓
Schema Mapper
        ↓
SELECT-only Safety Check
        ↓
Spider SQLite
        ↓
Query Result
        ↓
Vietnamese Natural Answer
```

Kiến trúc Web:

```text
React Frontend
      ↓
FastAPI Backend
      ↓
Text-to-SQL Pipeline
      ↓
Spider SQLite
```

---

## 2. Mô hình và phương pháp

### Qwen2.5-Coder-3B-Instruct

Hệ thống sử dụng **Qwen2.5-Coder-3B-Instruct** làm mô hình nền (Backbone LLM) cho nhiệm vụ sinh câu lệnh SQL từ câu hỏi tiếng Việt và thông tin lược đồ.

### QLoRA

Mô hình được tinh chỉnh bằng **QLoRA 4-bit** với cấu hình chính:

- Quantization: NF4 4-bit
- Double Quantization: enabled
- LoRA rank: `r = 16`
- LoRA alpha: `32`
- LoRA dropout: `0.05`
- Compute dtype: `float16`

Các module áp dụng LoRA:

```text
q_proj
k_proj
v_proj
o_proj
gate_proj
up_proj
down_proj
```

### DEW

DEW được sử dụng để tăng cường thông tin liên kết giữa câu hỏi tiếng Việt và lược đồ cơ sở dữ liệu.

Cơ chế thực hiện:

1. Đối sánh n-gram trong câu hỏi với từ điển lược đồ theo từng `db_id`.
2. Ưu tiên cụm khớp dài nhất.
3. Gán nhãn thực thể bảng và cột.
4. Giữ lại nhiều ứng viên khi xuất hiện trường hợp nhập nhằng.

Ví dụ:

```text
Có tất cả bao nhiêu kiến trúc sư nữ?
```

sau DEW:

```text
Có tất cả bao nhiêu [TABLE: kiến trúc sư] nữ?
```

### E3 Schema-aware Constrained Candidate Decoding

E3 kiểm tra SQL được sinh bởi E2. Khi phát hiện vi phạm lược đồ, hệ thống sinh nhiều SQL ứng viên bằng beam decoding, loại các ứng viên vi phạm lược đồ và lựa chọn ứng viên hợp lệ có điểm mô hình cao nhất.

E3 chỉ được kích hoạt khi SQL của E2 xuất hiện vi phạm lược đồ.

---

## 3. Kết quả thực nghiệm

Đánh giá được thực hiện trên **954 mẫu thuộc tập Dev của ViText2SQL**.

| Configuration | EM | SQL Validity | EA | SHR |
|---|---:|---:|---:|---:|
| E1 - QLoRA | 50.94% | 88.99% | 63.94% | 4.09% |
| E2 - QLoRA + DEW | 52.10% | 89.73% | 64.57% | 2.73% |
| E3 - E2 + Constrained Decoding | **52.73%** | **91.93%** | **65.41%** | **0.31%** |

Trong đó:

- **EM**: Exact Matching
- **EA**: Execution Accuracy
- **SQL Validity**: tỷ lệ SQL có thể thực thi
- **SHR**: Schema Hallucination Rate

So với E2, E3:

- tăng EM `+0.63` điểm phần trăm;
- tăng SQL Validity `+2.20` điểm phần trăm;
- tăng EA `+0.84` điểm phần trăm;
- giảm SHR `-2.42` điểm phần trăm.

---

## 4. Cấu trúc project

```text
ViText2SQL_web/
│
├── backend/
│   ├── routers/
│   ├── services/
│   ├── tests/
│   └── main.py
│
├── database/
│   ├── schema.sql
│   └── seed.sql
│
├── evaluation/
│   └── final_metrics.json
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
├── nlp/
│   ├── dew_dictionary.json
│   └── pipeline.py
│
├── notebook/
│   ├── training.ipynb
│   └── training e2_e3.ipynb
│
├── .env.example
├── .gitignore
└── README.md
```

---

## 5. Dữ liệu và mô hình

Dataset và model weights **không được lưu trực tiếp trong repository**.

Các thành phần cần chuẩn bị riêng gồm:

```text
data/
├── train.json
├── dev.json
├── test.json
└── tables.json
```

Spider databases:

```text
database/
└── spider/
    ├── database_1/
    │   └── database_1.sqlite
    ├── database_2/
    │   └── database_2.sqlite
    └── ...
```

QLoRA adapter:

```text
model/
└── e2_qlora_dew_final/
```

Các thư mục/file trên đã được loại khỏi Git bằng `.gitignore`.

---

## 6. Cài đặt Backend

Tạo Python virtual environment:

```powershell
python -m venv .venv
```

Kích hoạt môi trường trên Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Cài đặt dependencies:

```powershell
pip install -r backend/requirements-web.txt
```

Khởi động FastAPI:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Backend mặc định chạy tại:

```text
http://127.0.0.1:8000
```

---

## 7. Cài đặt Frontend

Di chuyển vào thư mục frontend:

```powershell
cd frontend
```

Cài đặt dependencies:

```powershell
npm install
```

Khởi động React/Vite:

```powershell
npm run dev
```

Frontend mặc định chạy tại:

```text
http://localhost:5173
```

---

## 8. API chính

Một số API chính của hệ thống:

```text
GET  /nlp/status
GET  /api/databases
GET  /api/databases/{db_id}/schema
POST /api/databases/{db_id}/execute
POST /api/query
```

`POST /api/query` thực hiện pipeline chính:

```text
Question
→ DEW
→ E2
→ E3 (if required)
→ Schema Mapping
→ SQL Safety
→ SQLite Execution
→ Natural Answer
```

---

## 9. An toàn truy vấn

Ứng dụng Web chỉ cho phép thực thi truy vấn đọc dữ liệu (`SELECT`).

Các thao tác thay đổi cơ sở dữ liệu như:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
```

không được phép thực thi thông qua API truy vấn của hệ thống.

---

## 10. Công nghệ sử dụng

- Python
- PyTorch
- Transformers
- PEFT / QLoRA
- BitsAndBytes
- SQLGlot
- FastAPI
- React
- Vite
- SQLite
- PostgreSQL (prototype)
- Qwen2.5-Coder-3B-Instruct

---

## 11. Giới hạn hiện tại

Hệ thống hiện vẫn còn một số giới hạn:

- Chưa xử lý đầy đủ bài toán ánh xạ giá trị (value grounding) giữa cách diễn đạt trong câu hỏi và giá trị thực tế trong cơ sở dữ liệu.
- Một số truy vấn `JOIN` phức tạp vẫn có thể đúng cú pháp nhưng chưa chính xác về ngữ nghĩa.
- Kết quả thực nghiệm chính được đánh giá trên tập Dev của ViText2SQL.
- Phiên bản Web cuối sử dụng Spider SQLite để bảo đảm tính nhất quán với quá trình đánh giá Execution Accuracy.

PostgreSQL được sử dụng trong giai đoạn prototype để kiểm tra kết nối backend và cơ sở dữ liệu, không phải cơ sở dữ liệu thực thi của pipeline Text-to-SQL cuối.

---

## 12. Repository

Repository chứa:

- Source code huấn luyện và đánh giá
- NLP pipeline
- DEW dictionary
- E3 constrained decoding
- Backend FastAPI
- Frontend React
- Schema mapper
- Evaluation metrics
- Notebook thực nghiệm

Dataset ViText2SQL, Spider databases và model weights không được phân phối trực tiếp trong repository.