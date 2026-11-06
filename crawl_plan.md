# Kế hoạch crawl tin tức 2026

Mục tiêu: thử cách lấy dữ liệu tối thiểu, kiểm tra kết quả rồi mới crawl diện rộng. Ưu tiên **Tuổi Trẻ, Thanh Niên, VietnamNet** để đồng nhất với dữ liệu lịch sử; VnExpress bổ sung sau. Giữ nguyên 3 CSV lịch sử hiện có.

## 1. Schema chung tối thiểu

**Chốt schema trước khi viết crawler**, để mỗi thành viên trả về cùng cấu trúc. Crawler chỉ cần lấy 6 trường bắt buộc; `article_id` do code tạo, không cần lấy từ website.

| Trường | Yêu cầu |
| --- | --- |
| `title` | Tiêu đề bài |
| `content` | Thân bài dạng text, giữ dấu tiếng Việt và đoạn văn |
| `source` | Một trong: `Tuổi Trẻ`, `Thanh Niên`, `VietnamNet` |
| `url` | URL bài gốc; bỏ fragment và tham số tracking đã xác định, giữ tham số có ý nghĩa |
| `published_at` | Thời điểm đăng lấy từ bài, ISO 8601 có múi giờ; thống nhất `+07:00` |
| `collected_at` | Thời điểm crawler lấy bài, cùng định dạng thời gian |
| `article_id` | SHA-256 của `source + "|" + url` sau quy tắc URL thống nhất |

`description`, `category` lấy thêm nếu dễ; thiếu thì để trống. Chưa bắt buộc author, tags, NER hoặc event_id. Không dùng ngày cập nhật/ngày crawl thay ngày đăng.

Khi tích hợp lịch sử: ánh xạ `public_date` → `published_at`, thống nhất source và tạo ID cùng quy tắc. `collected_at` lịch sử để trống vì không có thông tin. Làm trên bản dữ liệu riêng, giữ nguyên raw; không cần hoàn tất việc này trước khi thử crawler.

## 2. Crawl thử

- Mỗi nguồn thử **30 URL bài báo**: khoảng 20 bài gần đây và 10 bài cũ trong năm 2026, trải ít nhất 2 tháng. Có bài đầu năm nếu tìm được để kiểm tra backfill.
- Có thể chia một người phụ trách một nguồn. Dùng chung schema và quy tắc tạo ID/URL.
- Ưu tiên RSS, sitemap hoặc trang lưu trữ được phép truy cập; tải tuần tự, có khoảng nghỉ và retry giới hạn. Gặp chặn truy cập thì ghi lỗi, không tìm cách vượt chặn.
- Lưu bài hợp lệ thành CSV UTF-8. Với URL lỗi, ghi URL và lý do; không điền giả dữ liệu hoặc bỏ lỗi âm thầm.

**Mỗi nguồn đạt yêu cầu khi:**

- Ít nhất **27/30 URL** lấy được đủ 6 trường bắt buộc; ngày đăng đọc được và hợp lý so với bài gốc. Đây là ngưỡng thử đề xuất của nhóm.
- Không có ID/URL lặp trong các bản ghi hợp lệ; ngày thiếu múi giờ phải được phát hiện và xử lý theo quy tắc thống nhất.
- Kiểm tra thủ công **5 bài mỗi nguồn**, gồm bài mới và cũ: đúng tiêu đề, ngày đăng, thân bài; không lấy menu/quảng cáo làm content.
- Lấy được cả bài cũ và mới. Nếu chưa truy xuất được đầu năm, ghi rõ chưa kiểm chứng khả năng backfill cả năm.

Chỉ cần một bảng tóm tắt: nguồn, URL thử, bài hợp lệ, lỗi, thiếu trường, URL trùng và kết quả xem thủ công. Content dưới 200 ký tự được gắn cờ xem lại, chưa tự động loại.

## 3. Chuyển sang crawl thật

Nguồn nào đạt phần thử thì mở rộng nguồn đó; nguồn lỗi tiếp tục sửa và thử lại.

1. Backfill bài từ **01/01/2026 đến ngày chạy**; ghi rõ khoảng nào chưa lấy được.
2. Chia đợt theo **nguồn × tháng**; thử một đợt trước khi chạy phần còn lại. Lưu sau mỗi đợt để tiếp tục khi gián đoạn.
3. Dùng URL/ID để tránh tải lại. Giữ bài khác nguồn cùng đưa tin; chưa deduplicate theo nội dung.
4. Sau backfill, cập nhật hằng ngày. Mỗi đợt kiểm tra số bài, trường thiếu và ngày đăng; không suy ra độ phủ đầy đủ chỉ vì không có lỗi.

Chưa cần database, scheduler phức tạp, preprocessing toàn bộ hoặc mô hình ML ở bước này.

## 4. Lưu dữ liệu cho nhóm

**Đề xuất ban đầu: GitHub lưu code/tài liệu, một thư mục Google Drive chung lưu dataset.** Drive cho phép chia sẻ theo thành viên và phân quyền xem/chỉnh sửa; cần kiểm tra dung lượng tài khoản của nhóm. [Hướng dẫn chia sẻ](https://support.google.com/drive/answer/7166529?hl=en).

| Nơi | Lưu gì |
| --- | --- |
| GitHub | Crawler, notebook, schema/kế hoạch và hướng dẫn tải dữ liệu |
| Drive chung | CSV lịch sử, mẫu crawl, các đợt crawl 2026 và log lỗi |
| Máy mỗi thành viên | Bản local trong `data/` để chạy code |

Tên file đề xuất: `sample_tuoitre.csv`, `tuoitre_2026-01.csv`; dùng `thanhnien` và `vietnamnet` tương tự. Khi cập nhật một tháng, tải bản đã chốt về, bổ sung rồi xuất lại; chỉ một người phụ trách ghi file của nguồn đó tại một thời điểm.

Một người phụ trách dữ liệu chung: nhận file từng nguồn, kiểm tra schema/ID và chốt phiên bản có ngày, ví dụ `v1_2026-11-06`. Không ghi đè bản đã chốt; ghi link Drive và phiên bản trong tài liệu GitHub. Không cần thêm DVC/Git LFS ở giai đoạn đầu.

Các file dữ liệu lớn phải được bỏ khỏi Git bằng `.gitignore` dùng chung cho cả nhóm. GitHub Git thông thường chặn file trên 100 MiB. [Giới hạn file](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). Bản dataset gốc trên Hugging Face vẫn là nguồn tải lại khi cần.
