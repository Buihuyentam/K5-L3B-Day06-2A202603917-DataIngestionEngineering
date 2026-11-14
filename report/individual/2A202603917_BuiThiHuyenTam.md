# Báo cáo cá nhân — Day 6

**Học viên:** Bui Thi Huyen Tam · **MSSV:** 2A202603917 · **Lớp:** L3B
**Repository:** [Buihuyentam/K5-L3B-Day06-2A202603917DataIngestionEngineering](https://github.com/Buihuyentam/K5-L3B-Day06-2A202603917DataIngestionEngineering)

## Dữ liệu và pipeline

- **Nguồn:** NIST SP 800-63B-4, *Digital Identity Guidelines: Authentication and Authenticator Management*, bản cuối tháng 07/2025. Nguồn gốc: [NIST publication record](https://csrc.nist.gov/pubs/sp/800/63/b/4/final) và PDF chính thức.
- **Quyền:** trang 3 của PDF cho biết tài liệu có thể được các tổ chức phi chính phủ sử dụng tự nguyện và không thuộc copyright tại Hoa Kỳ; NIST technical-series policy ghi rõ quyền đối với một số tác phẩm và cảnh báo một số ấn phẩm có tác giả bên thứ ba. Tài liệu này liệt kê đồng tác giả là nhà thầu. Đã ghi nguồn/ghi công; cần xác minh quyền theo khu vực trước khi tái sử dụng ngoài bài tập. Xem [`manifest.json`](../../starter/data/manifest.json).
- **Quy tắc trang:** PDF có 129 trang vật lý. Dùng trang vật lý 12–109 (98 trang có nội dung, gồm thân tài liệu và Appendix A–B); loại bìa/front matter, mục lục, acronym list, glossary, change log và references. Trang benchmark là số trang vật lý 1-based, không phải số in ở chân trang.
- **Trích xuất:** pypdf 6.21.4; không OCR. Chạy thực tế: 0 trang trống, 0 trang lỗi, 0 ký tự thay thế được ghi nhận trong phạm vi chọn. SHA-256 và số ký tự từng trang nằm trong [`manifest.json`](../../starter/data/manifest.json); tóm tắt lỗi ở [`ingestion_report.json`](../../starter/results/ingestion_report.json).
- **Embedding:** FastEmbed 0.7.3, `sentence-transformers/all-MiniLM-L6-v2`, 384 chiều; cùng encoder cho query/document, không thêm query prefix. Đã chạy probe query và document; cả hai trả 384 chiều. Chạy local, không API key, chi phí API $0.
- **Store:** PostgreSQL 16.16 + pgvector 0.8.7, Docker image `pgvector/pgvector:0.8.7-pg16`, exact cosine distance (`<=>`). Setup check thành công: `python scripts/check_setup.py`.
- **Metadata:** `document_id`, `source`, `page`, `source_id`, `section`. `section` là heading cấp cao được trích từ từng trang; filter nhận `section` do câu hỏi cung cấp. Các câu C không có filter từ gold answer/source.

## Cấu hình và benchmark

- **A:** fixed windows 700 ký tự, overlap 100.
- **B:** paragraph-aware, tối đa 900 ký tự; tiêu đề được gắn với nội dung kế tiếp.
- **C:** cùng chunk và vector như B; chỉ thêm exact filter `section` khi câu hỏi nêu section.
- **Benchmark:** [`questions.json`](../../starter/benchmark/questions.json), 20 câu (15 dev / 5 test), tất cả có quote/page gold đã kiểm tra tự động trên PDF. Có 10 câu có section filter, gồm 5 câu test.
- **Chọn cấu hình:** quy tắc [`selection_criteria.md`](../../starter/benchmark/selection_criteria.md) được ghi trước thí nghiệm. Chọn C sau dev vì Evidence Hit@3 13/15, so với B 12/15 và A 9/15; C hòa B về Hit@1 ở 9/15. Test không dùng để chọn.
- **Lịch sử test:** pilot v1 đã được mở; pilot phát hiện chunk paragraph chỉ chứa heading. Đã sửa và kiểm thử lỗi này, lưu pilot trong [`results/pilot_v1/`](../../starter/results/pilot_v1/), rồi thay 5 câu test bằng v2 trên trang khác trước lần chạy cuối. Theo [`test_set_history.md`](../../starter/benchmark/test_set_history.md), test v2 là **exploratory, không phải holdout độc lập**.

## Kết quả retrieval

| Strategy | Split | Hit@1 | Evidence Hit@3 | Chunk count | Embed time | Ingest/index time | API cost |
|---|---|---:|---:|---:|---:|---:|---:|
| A | Dev | 4/15 (26.7%) | 9/15 (60.0%) | 403 | 31.059 s | 32.818 s | $0 |
| A | Test v2 | 2/5 (40.0%) | 5/5 (100%) | 403 | — | — | $0 |
| B | Dev | 9/15 (60.0%) | 12/15 (80.0%) | 311 | 32.867 s | 34.454 s | $0 |
| B | Test v2 | 2/5 (40.0%) | 3/5 (60.0%) | 311 | — | — | $0 |
| C | Dev | 9/15 (60.0%) | 13/15 (86.7%) | 311 | 0 s reused | 1.121 s incremental | $0 |
| C | Test v2 | 3/5 (60.0%) | 4/5 (80.0%) | 311 | — | — | $0 |

Chi tiết đầy đủ theo câu, top-3 text/score/source/page/metadata và hit flags: [`traces.jsonl`](../../starter/results/traces.jsonl). C tái sử dụng 311 vector B giống hệt; vì vậy 1.121 giây là thời gian incremental index, không phải ingest độc lập. Ước lượng C nếu cộng thời gian embedding của B là 33.988 giây; phép đo thực tế không tách nhiễu hệ thống.

### So sánh và audit thủ công

- **A–B (chunking):** B hơn A 3 câu Evidence Hit@3 và 5 câu Hit@1 trên dev; giảm 92 chunk. Chunk coherence trung bình tăng từ 1.0/2 lên 1.2/2 trên cùng 10 trang vật lý 12–21. B mất 1.636 giây trong lần đo nhưng vẫn có các chunk cắt giữa mệnh đề.
- **B–C (filter):** C hơn B 1 câu Evidence Hit@3 trên dev, Hit@1 bằng nhau; chunk và coherence giống nhau. Trong test v2, C đạt 4/5 Evidence Hit@3 so với B 3/5, nhưng tập nhỏ và không độc lập. Filter thu hẹp phạm vi đúng metadata, không đảm bảo lấy được chunk chứa đủ evidence.
- **Coherence:** A 1.0/2 (10 vị trí), B 1.2/2, C 1.2/2. B/C chia sẻ cùng chunk. Từng chunk, điểm và lý do được lưu trong [`manual_audit.json`](../../starter/results/manual_audit.json).
- **Metadata:** 45/45 bản ghi top-3 test có source/page/section khớp với trang PDF đã trích. C tuân thủ filter 15/15 hit trong 5/5 câu có filter. Kiểm tra từng dòng ở [`metadata_audit.json`](../../starter/results/metadata_audit.json). `section` giúp thu hẹp chủ đề và truy nguồn, nhưng section-level filter quá rộng để phân biệt tiểu mục có cùng chủ đề.
- **Grounding (không phải độ chính xác câu trả lời LLM):** trên 5 test v2, A có 0/1/2 = 0/0/5, trung bình 2.0; B = 0/2/3, trung bình 1.6; C = 0/1/4, trung bình 1.8. Điểm từng câu/lý do và liên kết trace ở [`manual_audit.json`](../../starter/results/manual_audit.json). Đây là nhãn AI-assisted, không chấm mù độc lập; học viên cần xác nhận.
- **Lỗi tiêu biểu:** B/C q04 dev truy xuất các trang Appendix A về password strength thay vì requirement verifier ở trang 25; C q08 dev lọc không áp dụng vì query không nêu section và lấy recovery trang 61–62 thay vì physical-authenticator trang 41. Test v2: B/C q16 có ngữ cảnh biometric nhưng bỏ lỡ ngưỡng FMR 1/10,000; B q19 lấy định nghĩa timeout nhưng thiếu hành động UX. Danh sách miss và giải thích ở [`failure_analysis.md`](../../starter/results/failure_analysis.md).

## Kết luận, giới hạn và tái lập

Chọn **C** theo tiêu chí dev đã khóa: hiệu quả Evidence Hit@3 cao nhất và Hit@1 không kém B; filter chỉ có ích khi phạm vi section được nêu rõ trước truy xuất. Tuy vậy, A đạt 5/5 Evidence Hit@3 trên test v2 và C đạt 4/5; không suy rộng từ năm câu test. Test v2 được tạo sau khi đã xem pilot v1, nên không được coi là holdout độc lập. Kết quả là retrieval evidence trên một tài liệu tiếng Anh; không đo khả năng trả lời của LLM.

Lệnh setup, chạy theo giai đoạn và test nằm trong [README](../../README.md); unit tests: `python -m unittest discover -s tests -v`. Công cụ AI: Copilot hỗ trợ hiện thực và phân tích; benchmark evidence được đối chiếu trực tiếp với PDF, pipeline dùng embedding thật và pgvector, không có mock vector hoặc LLM judge. Nguy cơ thiên lệch còn lại gồm tập test nhỏ, câu hỏi cùng một tài liệu và nhãn coherence/grounding do AI-assisted review.
