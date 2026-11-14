# Day 06 · Data Ingestion Engineering

Thí nghiệm retrieval cá nhân trên NIST SP 800-63B-4: cùng corpus, embedding và benchmark; so sánh A (fixed-size), B (paragraph-aware) và C (B + filter theo section). Đây là retrieval experiment, không tạo câu trả lời bằng LLM.

## Chạy trên Windows

Yêu cầu Python 3.11+, Docker Desktop đang chạy và mạng khi tải dependencies/model lần đầu. Trong PowerShell:

```powershell
Set-Location starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

`.env` dùng PostgreSQL local và model `sentence-transformers/all-MiniLM-L6-v2`; không cần API key. Không commit `.env`. PostgreSQL lưu vector bằng pgvector, exact cosine search (`<=>`).

Chạy dev trước, kiểm tra `results/metrics.json`, rồi ghi chiến lược và lý do dựa **chỉ trên dev** vào `results/selection.json` trước khi mở test:

```powershell
python -m src.run --split dev
# xem trace và chọn chiến lược dựa trên benchmark/selection_criteria.md
python -m src.run --split test
```

Lệnh test chủ động dừng nếu chưa có lựa chọn dev. Pipeline kiểm tra gold evidence, ghi trace top-3 đầy đủ và chạy lại upsert để xác nhận không tạo bản ghi trùng. Unit tests:

```powershell
python -m unittest discover -s tests -v
```

## Dữ liệu, benchmark và kết quả

- PDF: [starter/data/NIST.SP.800-63b-4.pdf](starter/data/NIST.SP.800-63b-4.pdf); nguồn chính thức [NIST SP 800-63B-4](https://csrc.nist.gov/pubs/sp/800/63/b/4/final), bản cuối tháng 07/2025.
- Quyền, SHA-256, 129 trang vật lý, cách chọn 98 trang nội dung, ký tự/trang và lỗi trích xuất: [starter/data/manifest.json](starter/data/manifest.json).
- 20 câu đã khóa (15 dev / 5 test), gold quote, physical page và filter: [starter/benchmark/questions.json](starter/benchmark/questions.json). Tiêu chí chọn cấu hình được ghi trước khi chạy tại [starter/benchmark/selection_criteria.md](starter/benchmark/selection_criteria.md).
- Lịch sử thay test sau pilot đã xem kết quả: [starter/benchmark/test_set_history.md](starter/benchmark/test_set_history.md).
- Top-3 text/score/source/metadata và nhãn retrieval: [starter/results/traces.jsonl](starter/results/traces.jsonl); metric: [starter/results/metrics.json](starter/results/metrics.json); tài nguyên và cấu hình: [starter/results/run_metadata.json](starter/results/run_metadata.json).
- Audit coherence/grounding: [starter/results/manual_audit.json](starter/results/manual_audit.json); kiểm tra metadata/filter: [starter/results/metadata_audit.json](starter/results/metadata_audit.json); lỗi retrieval: [starter/results/failure_analysis.md](starter/results/failure_analysis.md); log CSV: [artifacts/experiment_log.csv](artifacts/experiment_log.csv).
- Báo cáo cá nhân: [report/individual/2A202603917_BuiThiHuyenTam.md](report/individual/2A202603917_BuiThiHuyenTam.md).

Metadata `section` được lấy từ heading cấp cao trên trang. C chỉ áp dụng filter khi câu hỏi nêu section; A và B không filter. Test v2 thay bộ test sau khi xem pilot v1 để tránh gọi lại câu đã lộ; đây là đánh giá exploratory, không phải holdout độc lập. Hit/Evidence Hit đo retrieval evidence, không phải độ chính xác câu trả lời do LLM sinh.

## Giới hạn đã biết

- NIST SP 800-63B-4 là một tài liệu tiếng Anh, một phiên bản và một chủ đề; kết quả không khái quát sang corpus khác.
- Quyền sử dụng và ghi công dựa trên thông báo trong tài liệu và chính sách NIST; kiểm tra giới hạn theo khu vực pháp lý trước khi tái phân phối bên ngoài bài nộp này.
- PDF được trích bằng pypdf, không OCR. Trang trống/lỗi và ký tự thay thế được ghi trong manifest/report.
- Evidence Hit@3 tự động yêu cầu một chunk chứa nguyên văn quote trên đúng trang; evidence bị chia chunk hoặc diễn đạt tương đương có thể bị tính là miss. Nhãn coherence/metadata/grounding thủ công được lưu riêng.
- Model chạy local nên chi phí API là $0; thời gian gồm CPU, cache model và tải lần đầu có thể khác theo máy.

Xem [GUIDE.md](GUIDE.md), [BENCHMARK.md](BENCHMARK.md), [RULES.md](RULES.md) và [SUBMISSION.md](SUBMISSION.md) để biết tiêu chí lab.
