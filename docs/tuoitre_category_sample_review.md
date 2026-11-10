# Mẫu Tuổi Trẻ theo 18 chuyên mục — 07/11/2026

Branch: `feat/tuoitre-crawler`.

```powershell
python crawl_tuoitre.py category-sample --config config/tuoitre.json
python -m pytest -q
```

## Kết quả thực tế

- Đọc đủ 18 trang chuyên mục do người dùng cung cấp.
- Chọn 108 URL ứng viên (tối đa 6 mỗi nhóm); thử 40 lượt và lưu 36 bài.
- Đủ 2 bài hợp lệ mỗi nhóm; 0 category trống, 0 trường bắt buộc thiếu, 0 URL/ID trùng.
- Ngày đăng mẫu: 03/11/2026–07/11/2026, timezone +07:00; không chứng minh độ phủ cả năm.
- 17 tests PASS: category nguồn, Video, discovery, cross-listing, quota, resume, HTTP và các kiểm tra cũ.
- Chưa chạy full. Không commit/push.

| Chuyên mục | Bài hợp lệ |
|---|---:|
| Video | 2 |
| Thời sự | 2 |
| Thế giới | 2 |
| Pháp luật | 2 |
| Kinh doanh | 2 |
| Công nghệ | 2 |
| Xe | 2 |
| Du lịch | 2 |
| Nhịp sống trẻ | 2 |
| Văn hóa | 2 |
| Giải trí | 2 |
| Thể thao | 2 |
| Giáo dục | 2 |
| Nhà đất | 2 |
| Sức khỏe | 2 |
| Giả - Thật | 2 |
| Bạn đọc | 2 |
| Khoa học | 2 |

## Kiểm tra nhãn và nội dung

Nhãn là chuyên mục chính thức từ breadcrumb/meta của bài, chuẩn hóa tên theo config.
Video là nhóm cấp cao theo đường dẫn `/video/`, dù breadcrumb bên trong có thể là
Thế giới, Thể thao... Không suy diễn chuyên mục từ nội dung.

Đã đối chiếu toàn bộ 36 tiêu đề với HTML gốc và kiểm tra 5 bài sau ở mức HTML/text
(nhãn, ngày đăng, đoạn đầu/cuối và vùng thân bài; không phải kiểm thử browser):

| Nhóm | Bài đối chiếu | Bằng chứng |
|---|---|---|
| Video | [Tàu hỏa bốc cháy ở Ấn Độ](https://tuoitre.vn/video/tau-hoa-bat-ngo-boc-chay-du-doi-hon-1500-nguoi-thao-chay-o-an-do-204184.htm) | URL /video/; content 210 ký tự là sapo của nguồn, không phải transcript |
| Thời sự | [Tổ chức, biên chế quân đội](https://tuoitre.vn/dai-tuong-phan-van-giang-lam-viec-voi-bo-tong-tham-muu-tong-cuc-chinh-tri-ve-to-chuc-bien-che-quan-doi-100261106220530279.htm) | Breadcrumb và article:section đều là Thời sự |
| Nhà đất | [Tiêu chí đất bỏ hoang](https://tuoitre.vn/trong-ngoai-nghi-truong-dong-thuan-lam-ro-tieu-chi-dat-bo-hoang-100261106155620363.htm) | article:section là Nhà đất, dù được giới thiệu cả trên trang Thời sự |
| Giả - Thật | [Đe dọa đánh bom giả](https://tuoitre.vn/de-doa-danh-bom-gia-gay-nao-loan-hang-khong-chau-au-chien-dau-co-y-phai-xuat-kich-100261104083239286.htm) | article:section là Giả - Thật |
| Bạn đọc | [Văn bằng 2 và ngoại ngữ](https://tuoitre.vn/nen-bo-quy-dinh-dung-van-bang-2-mien-ngoai-ngu-dau-vao-dao-tao-thac-si-tien-si-100261106145415256.htm) | Breadcrumb và article:section đều là Bạn đọc |

## Bốn trường hợp ghi log

1. Bài đất bỏ hoang trên trang Thời sự có nhãn chính Nhà đất: không dùng làm mẫu Thời sự; được lưu khi crawl Nhà đất.
2. Bài “Phật giáo Việt Nam ngàn năm hộ quốc an dân”: HTML không có title/body theo selectors.
3. Bài tài khoản Facebook “Thanh Thật Thà” trên trang Giả - Thật có nhãn chính Pháp luật: không gán lại nhãn.
4. Bài “Nhẹ tay lúc bấm chốt đơn…” trên trang Bạn đọc không có category nhận diện thuộc danh sách: không điền nhãn giả.

URL và lý do đầy đủ nằm trong `data/tuoitre/category-sample_errors.jsonl`.
Các trường hợp này không bị ẩn; crawler thử URL tiếp theo trong giới hạn config để đạt quota.

## Artifacts và giới hạn

CSV: `data/tuoitre/sample_tuoitre_categories.csv`.
Manifest/report: `category-sample_urls.json`, `category-sample_report.json`.
HTML đối chứng: `data/tuoitre/category_sample_html/`.

Mẫu cũ 29 bài đã được khôi phục category từ HTML lưu sẵn, có backup và đối chiếu tất cả
các trường khác không đổi. Ba bài ngoài danh sách giữ nguyên nhãn nguồn, được ghi rõ trong
`sample_report.json`; CSV mới chỉ gồm 18 nhóm yêu cầu.

Đây là mẫu gần đây theo chuyên mục. Backfill cả năm, pagination đầy đủ của từng chuyên mục,
độ phủ lịch sử Video và layout đặc biệt chưa được xác minh. Tiếp tục dừng để người dùng xem mẫu.
