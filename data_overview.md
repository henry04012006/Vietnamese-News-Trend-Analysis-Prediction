# VietOnlineNews — Data overview

Kiểm tra ngày **2026-11-06**, revision `bd8d2a865c8981d34cb9d85f69f62bda7c40b520`. [Nguồn dữ liệu](https://huggingface.co/datasets/VLUS06/VietOnlineNews).

**Phạm vi:** 3 CSV raw trong `data/` và 4 CSV processed tải tạm từ cùng revision. Báo cáo chính dùng **text train/dev/test ghép metadata theo `id` trong RAM**; raw dùng đối chiếu. Không ghi lại dataset, không preprocessing hoặc training. SHA-256 các file đã khớp upstream; hash 3 CSV local trước/sau audit không đổi.

## 1. Dataset Overview

| Dataset | Rows | Columns |
| --- | --- | --- |
| Raw (3 nguồn) | 273,058 | 10 |
| Processed text (3 split) | 265,729 | 5 |
| Processed metadata | 265,729 | 8 |
| Processed sau ghép id | 265,729 | 11 cột gốc, gộp category sau đối chiếu |

| Split | Text rows | Matched rows | Min date | Max date |
| --- | --- | --- | --- | --- |
| train | 186,010 | 186,010 | 2023-01-01 | 2025-12-31 |
| dev | 39,859 | 39,859 | 2023-01-01 | 2025-12-31 |
| test | 39,860 | 39,860 | 2023-01-01 | 2025-12-31 |

**Cột và kiểu dữ liệu:** CSV không lưu schema kiểu dữ liệu. Audit đọc các cột bằng pandas `string` để giữ nguyên khóa; toàn bộ ID text và metadata chỉ gồm chữ số. Khi đọc thử 100 dòng đầu, pandas suy luận ID là `int64`; kiểm tra ngày được thực hiện riêng.

| File | Các cột |
| --- | --- |
| Raw (10 cột) | `category`, `sub_topic`, `title`, `description`, `content`, `public_date`, `author`, `source`, `url`, `tag` |
| Text (cả 3 split, 5 cột) | `id`, `title`, `description`, `content`, `category` |
| Metadata (8 cột) | `id`, `category`, `source`, `url`, `author`, `sub_topic`, `tag`, `public_date` |

| Trường | Kiểu kiểm tra trên toàn bộ dữ liệu |
| --- | --- |
| `id` | Chuỗi số; ép thử `int64` thành công, min=1, max=265,729 |
| `title`, `description`, `content`, `category` | `string` |
| `source`, `url`, `author`, `sub_topic`, `tag` | `string` |
| `public_date` | Chuỗi gốc; đọc được thành datetime có múi giờ trên toàn bộ processed |

Schema 3 split giống nhau. Các thống kê sau dùng toàn bộ dòng, không ngoại suy từ preview. Raw không có split.

## 2. Metadata Check

Text và metadata **chưa ghép sẵn trong CSV**. Audit đã ghép outer theo `id`, xác minh `one_to_one`:

| Kiểm tra | Số dòng |
| --- | ---: |
| Ghép được cả hai phía | 265,729 |
| Text không có metadata | 0 |
| Metadata không có text | 0 |
| ID trống: text / metadata | 0 / 0 |
| Category khác nhau sau ghép | 0 |

| Column | Raw | Merged |
| --- | --- | --- |
| title | 2 (0.001%) | 0 (0.000%) |
| content | 2,107 (0.772%) | 0 (0.000%) |
| source | 0 (0.000%) | 0 (0.000%) |
| public_date | 0 (0.000%) | 0 (0.000%) |
| url | 0 (0.000%) | 0 (0.000%) |

Missing = null hoặc chuỗi chỉ chứa khoảng trắng. Placeholder (`null`, `NA`, `None`, ...) được kiểm tra riêng: raw có 0 ô trong title/description/content, text processed có 0 ô; source/public_date/url trong metadata có 0 ô. Raw không có `id`, nên **không merge raw với metadata bằng thứ tự dòng**. Đối chiếu URL cho thấy 7,741 URL raw không có trong metadata và 412 URL metadata không có trong raw; chưa xác định nguyên nhân chênh lệch.

## 3. Duplicate Check

| Check | Raw extra rows | Raw groups | Merged extra rows | Merged groups |
| --- | --- | --- | --- | --- |
| ID | No id column | — | 0 | 0 |
| URL (trim) | 0 | 0 | 0 | 0 |
| Content exact | 2,012 | 392 | 0 | 0 |
| Content NFC + whitespace | 2,014 | 393 | 0 | 0 |

“Extra rows” = số dòng vượt dòng đầu của mỗi nhóm; bỏ nội dung trống khi đếm trùng content. Exact = chuỗi gốc giống hệt; NFC + khoảng trắng chỉ dùng tạo hash chẩn đoán, không sửa text. URL chỉ trim khoảng trắng, chưa canonicalize. ID xuất hiện ở nhiều split: **0**; nhóm content chuẩn hóa xuất hiện ở nhiều split: **0**; nhóm content này xuất hiện ở nhiều nguồn: **0**.

## 4. Temporal Coverage

| Dataset | Min date | Max date | Bad dates | Timezone assumed | Outside 2023–2025 |
| --- | --- | --- | --- | --- | --- |
| Raw | 2023-01-01 | 2025-12-31 | 0 | 6 | 0 |
| Merged | 2023-01-01 | 2025-12-31 | 0 | 0 | 0 |

| Dataset | Source | Min date | Max date | Zero days | Min/day | Median/day |
| --- | --- | --- | --- | --- | --- | --- |
| Raw | Tuổi Trẻ | 2023-01-01 | 2025-12-31 | 0 | 5 | 44 |
| Raw | Thanh Niên | 2023-01-01 | 2025-12-31 | 0 | 37 | 85 |
| Raw | VietnamNet | 2023-01-01 | 2025-12-31 | 0 | 55 | 113 |
| Merged | Tuổi Trẻ | 2023-01-01 | 2025-12-31 | 0 | 5 | 43.5 |
| Merged | Thanh Niên | 2023-01-01 | 2025-12-31 | 0 | 37 | 85 |
| Merged | VietnamNet | 2023-01-01 | 2025-12-31 | 0 | 53 | 107 |

### Số bài theo năm

| Dataset | Year | Tuổi Trẻ | Thanh Niên | VietnamNet |
| --- | --- | --- | --- | --- |
| Raw | 2023 | 10,321 | 26,260 | 39,319 |
| Raw | 2024 | 16,623 | 30,972 | 39,621 |
| Raw | 2025 | 26,066 | 38,785 | 45,091 |
| Merged | 2023 | 10,254 | 26,243 | 36,884 |
| Merged | 2024 | 16,473 | 30,828 | 37,341 |
| Merged | 2025 | 25,968 | 38,634 | 43,104 |

### Số bài processed sau ghép theo tháng

| Month | Tuổi Trẻ | Thanh Niên | VietnamNet |
| --- | --- | --- | --- |
| 2023-01 | 533 | 1,923 | 2,666 |
| 2023-02 | 702 | 1,900 | 2,689 |
| 2023-03 | 821 | 2,270 | 3,124 |
| 2023-04 | 872 | 2,050 | 2,952 |
| 2023-05 | 893 | 2,154 | 3,106 |
| 2023-06 | 873 | 2,192 | 2,922 |
| 2023-07 | 944 | 2,313 | 3,240 |
| 2023-08 | 901 | 2,406 | 3,356 |
| 2023-09 | 834 | 2,221 | 3,078 |
| 2023-10 | 908 | 2,257 | 3,219 |
| 2023-11 | 920 | 2,221 | 3,180 |
| 2023-12 | 1,053 | 2,336 | 3,352 |
| 2024-01 | 1,110 | 2,453 | 2,937 |
| 2024-02 | 835 | 2,051 | 2,334 |
| 2024-03 | 1,284 | 2,692 | 2,964 |
| 2024-04 | 1,411 | 2,763 | 3,188 |
| 2024-05 | 1,366 | 2,662 | 3,176 |
| 2024-06 | 1,262 | 2,489 | 3,381 |
| 2024-07 | 1,453 | 2,428 | 3,286 |
| 2024-08 | 1,447 | 2,831 | 3,266 |
| 2024-09 | 1,372 | 2,372 | 2,962 |
| 2024-10 | 1,643 | 2,501 | 3,308 |
| 2024-11 | 1,704 | 2,676 | 3,168 |
| 2024-12 | 1,586 | 2,910 | 3,371 |
| 2025-01 | 1,294 | 2,447 | 2,711 |
| 2025-02 | 1,326 | 2,401 | 2,526 |
| 2025-03 | 1,758 | 2,968 | 2,931 |
| 2025-04 | 1,886 | 3,152 | 3,362 |
| 2025-05 | 2,043 | 3,000 | 3,833 |
| 2025-06 | 2,183 | 3,071 | 3,964 |
| 2025-07 | 2,408 | 3,508 | 4,256 |
| 2025-08 | 2,347 | 3,508 | 4,128 |
| 2025-09 | 2,327 | 3,356 | 3,734 |
| 2025-10 | 2,871 | 3,802 | 4,040 |
| 2025-11 | 2,680 | 3,987 | 3,750 |
| 2025-12 | 2,845 | 3,434 | 3,869 |

### Khoảng cần xem lại

| Dataset | Source | Type | Start | End | Days | Min/day |
| --- | --- | --- | --- | --- | --- | --- |
| Raw | Tuổi Trẻ | <25% median | 2023-01-23 | 2023-01-26 | 4 | 5 |
| Merged | Tuổi Trẻ | <25% median | 2023-01-23 | 2023-01-26 | 4 | 5 |

Ngưỡng sàng lọc: chuỗi ≥2 ngày liên tiếp có số bài **<25% median/ngày của chính nguồn trong 2023–2025**, hoặc có ngày 0 bản ghi. Đây chỉ là mức đưa tin thấp quan sát được; **không đủ bằng chứng kết luận crawler thiếu dữ liệu**. Có bài ở đủ 1.096 ngày cũng không chứng minh đã thu thập đầy đủ bài. Ngày có offset được quy về Asia/Ho_Chi_Minh; ngày thiếu offset được gắn cờ và giả định cùng múi giờ chỉ để audit.

## 5. Source & Category Distribution

| Source | Rows | Percent | Raw rows |
| --- | --- | --- | --- |
| Thanh Niên | 95,705 | 36.02 | 96,017 |
| Tuổi Trẻ | 52,695 | 19.83 | 53,010 |
| VietnamNet | 117,329 | 44.15 | 124,031 |

| Category | Tuổi Trẻ | Thanh Niên | VietnamNet | Total |
| --- | --- | --- | --- | --- |
| Giải trí | 10,290 | 14,642 | 15,932 | 40,864 |
| Kinh doanh | 8,257 | 10,161 | 14,824 | 33,242 |
| Thể thao | 5,836 | 8,557 | 17,885 | 32,278 |
| Thời sự | 5,290 | 11,403 | 10,706 | 27,399 |
| Giáo dục | 4,223 | 9,306 | 8,904 | 22,433 |
| Khoa học công nghệ | 970 | 12,795 | 7,243 | 21,008 |
| Đời sống | 0 | 8,960 | 10,156 | 19,116 |
| Xe | 5,366 | 5,258 | 8,181 | 18,805 |
| Sức khỏe | 4,521 | 3,418 | 8,727 | 16,666 |
| Thế giới | 4,181 | 5,623 | 5,043 | 14,847 |
| Du lịch | 1,003 | 5,582 | 2,594 | 9,179 |
| Bất động sản | 1,258 | 0 | 5,378 | 6,636 |
| Pháp luật | 1,500 | 0 | 1,756 | 3,256 |

Raw có 24 nhãn category khác nhau; processed có 13. Nhãn raw và processed được thống kê riêng, không tự ánh xạ category.

## 6. Text Quality

Độ dài = số ký tự, tính cả khoảng trắng; không phải số token. “Quá ngắn” ở đây chỉ là cờ **1–199 ký tự**, không phải tiêu chí tự động loại bài.

| Dataset | Source | Empty | 1–199 chars | Median chars | P95 chars | Min chars | Max chars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Raw | Thanh Niên | 294 | 2 | 2,765 | 6,853 | 0 | 34,909 |
| Raw | Tuổi Trẻ | 13 | 37 | 3,299 | 6,879 | 0 | 163,525 |
| Raw | VietnamNet | 1,800 | 4,259 | 2,472 | 5,530 | 0 | 62,323 |
| Merged | Thanh Niên | 0 | 0 | 2,761 | 6,828 | 260 | 34,857 |
| Merged | Tuổi Trẻ | 0 | 0 | 3,277 | 6,830 | 211 | 163,370 |
| Merged | VietnamNet | 0 | 1 | 2,576 | 5,576 | 197 | 62,312 |

## 7. Kết luận và việc cần làm trước dữ liệu crawl 2026

**Đủ trường để bắt đầu Event Detection và xây dựng chuỗi mức độ đưa tin:** text processed ghép được 265,729/265,729 bài, có tiêu đề/nội dung, nguồn, ngày và URL với tỷ lệ thiếu như bảng trên. Tuy nhiên, audit schema **không chứng minh chất lượng event clustering hay khả năng dự đoán trend**. Dữ liệu không có `event_id` hoặc nhãn emerging trend; cần xây tracking, gán nhãn đánh giá và backtest theo thời gian.

Trước khi tích hợp 2026:

1. Thống nhất schema, khóa ID có namespace và mapping nguồn/category. ID processed hiện chỉ được xác minh trong snapshot này; raw không có ID. `collected_at` không có trong các file được kiểm tra, cần lưu cho crawl mới; không dùng ngày tải dataset thay ngày crawl gốc.
2. Quyết định cách xử lý text trống/ngắn và content lặp theo kết quả trên; phân biệt crawl trùng, bản cập nhật và đăng lại giữa báo trước khi đếm số bài/nguồn. Không tự động loại mọi nội dung giống nhau.
3. Thống nhất timezone và phân biệt ngày đăng/cập nhật; xem lại 6 ngày raw thiếu offset. Kiểm tra những khoảng có số bài thấp và độ đầy đủ crawl bằng log/nguồn đối chứng.
4. Tự chia train/validation/test **theo thời gian**: cả ba split upstream đều trải qua 2023–2025, nên không thể dùng nguyên split cho forecast. Features và trạng thái tracking tại t chỉ dùng thông tin đã có đến t.
5. Giải thích chênh lệch URL raw/processed trước khi chọn corpus lịch sử chuẩn. So sánh 2026 trên 3 nguồn chung; VnExpress cần được xử lý riêng khi chưa có lịch sử tương thích.

**Giới hạn:** không kiểm tra URL còn truy cập được, độ chính xác nội dung/ngày đăng, độ đầy đủ so với toàn bộ bài trên website hay nhãn sự kiện thủ công. Không suy diễn nguyên nhân các chênh lệch chỉ từ số lượng.
