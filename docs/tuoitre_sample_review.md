# Đối chiếu mẫu Tuổi Trẻ — 07/11/2026

Branch: `feat/tuoitre-crawler`. Lệnh: `python crawl_tuoitre.py sample --config config/tuoitre.json`.

## Kết quả

| Kiểm tra | Quan sát |
|---|---|
| URL thử | 30: 20 mới, 10 đầu năm |
| Bài hợp lệ | 29: 19 mới + 10 cũ; đạt ngưỡng 27 |
| Thiếu trường bắt buộc | 0 |
| URL/ID trùng | 0 / 0 |
| Content dưới 200 ký tự | 0 |
| Ngày đăng | 01/01/2026–07/11/2026; offset +07:00 |
| Tests | 10 passed |
| Chạy lại | Không thêm bản ghi trùng; URL lỗi tiếp tục được ghi log |

## Đối chiếu 5 bài

Đọc HTML gốc lưu cùng lượt crawl và đối chiếu với CSV: tiêu đề, ngày hiển thị,
đoạn đầu/cuối, cấu trúc thân bài và các khối bị loại. Đây là kiểm tra HTML/text,
không phải kiểm thử giao diện bằng browser hoặc đánh giá tính đúng đắn của tin tức.

| Bài | Ngày hiển thị (GMT+7) | Content (ký tự) | Kết quả |
|---|---|---:|---|
| [Nhà máy điện gió Gia Lai](https://tuoitre.vn/gia-lai-khoi-cong-nha-may-dien-gio-7700-ti-dong-du-kien-phat-503-trieu-kwh-moi-nam-100261107062424428.htm) | 07/11/2026 08:57 | 1.696 | Tiêu đề/ngày đúng; thân bài riêng, loại related news và chú thích ảnh |
| [Phát điện từ núi lửa ngầm](https://tuoitre.vn/lan-dau-phat-dien-du-tu-nui-lua-ngam-duoi-day-dai-duong-100261106135102785.htm) | 07/11/2026 08:10 | 2.159 | Giữ nội dung và lỗi chính tả nguồn, không tự sửa văn bản |
| [Trương Lăng Hách](https://tuoitre.vn/truong-lang-hach-tu-vo-danh-den-dinh-luu-cbiz-chi-sau-nua-nam-100261106152257303.htm) | 07/11/2026 07:15 | 2.430 | Giữ các tiêu đề phụ/đoạn văn, không đưa related box vào text |
| [Tin thế giới ngày 1-1](https://tuoitre.vn/tin-tuc-the-gioi-1-1-chao-nam-2026-voi-hi-vong-hoa-binh-nga-ukraine-ve-binh-quoc-gia-my-rut-di-20260101065716406.htm) | 01/01/2026 07:05 | 7.394 | Giữ nhiều mục trong một bài; phần chữ trong khối content còn nguyên |
| [U23 Iraq](https://tuoitre.vn/trang-sina-mung-ra-mat-vi-u23-iraq-gap-kho-truoc-tran-dau-voi-trung-quoc-20260106064324541.htm) | 06/01/2026 06:52 | 1.371 | Đúng bài đầu năm, không lẫn liên kết gợi ý |

Không thấy menu/quảng cáo lẫn trong text của 5 bài đã xem. Giây trong `published_at`
lấy từ thuộc tính datetime của nguồn; giao diện chỉ hiển thị phút.

## URL lỗi và giới hạn

[Phật giáo Việt Nam ngàn năm hộ quốc an dân](https://tuoitre.vn/phat-giao-viet-nam-ngan-nam-ho-quoc-an-dan-100261105122316373.htm)
trả về HTML không có tiêu đề/thân bài theo selectors hiện tại. Ghi lỗi
`Missing title or article body`, không tạo dữ liệu giả hoặc thay bằng URL khác để tăng tỷ lệ thành công.
Chưa xác định cần hỗ trợ layout nào cho URL này.

Ở lượt crawl đầu, `category` trống. Sau yêu cầu crawl theo chuyên mục, CSV này đã được
bổ sung nhãn từ HTML gốc, giữ nguyên các trường khác và lưu bản trước cập nhật trong
`data/tuoitre/sample_tuoitre_before_categories.csv`. Ba bài có nhãn ngoài danh sách 18 nhóm
(`Cần biết`: 1, `Tin tức thị trường`: 2) được giữ nhãn nguồn, không gán lại. Mẫu mới đủ
18 nhóm nằm trong `sample_tuoitre_categories.csv`, xem [báo cáo mới](tuoitre_category_sample_review.md).

Mẫu cũ chủ yếu kiểm tra
hai giai đoạn đầu năm và hiện tại, không đại diện cho mọi tháng hoặc mọi layout.
Chưa kiểm chứng backfill toàn năm. Cần xem CSV và thống nhất xử lý layout lỗi trước
khi chạy thử một tháng, rồi mới mở rộng. Chưa chạy full theo yêu cầu người dùng.
