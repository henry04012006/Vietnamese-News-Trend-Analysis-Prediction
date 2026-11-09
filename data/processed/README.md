# Dữ liệu `data/processed/`

Thư mục này chứa dữ liệu bài báo đã làm sạch (Phase 2) và kết quả gom bài thành sự kiện (Phase 3). Đây là đầu vào cho Phase 4–5: tính thống kê theo event × ngày, tạo feature và label.

## Tổng quan

| | |
|---|---|
| Số bài | **463.995** |
| Khoảng thời gian | 01/01/2023 → 07/11/2026 (ngày 07/11/2026 mới crawl được một phần) |
| Nguồn | Thanh Niên, Tuổi Trẻ, VietnamNet |
| Số event | **320.842**, trong đó 272.630 event (85%) chỉ có 1 bài |
| Event từ 2 bài | 48.212 |
| Event từ 5 bài | 6.759 |
| Event từ 20 bài | 869 |
| Múi giờ | Asia/Ho_Chi_Minh (+07:00) |

Số bài theo năm:

| Năm | Thanh Niên | Tuổi Trẻ | VietnamNet | Tổng |
|---|---:|---:|---:|---:|
| 2023 | 26.243 | 10.254 | 36.884 | 73.381 |
| 2024 | 30.828 | 16.472 | 37.340 | 84.640 |
| 2025 | 38.634 | 25.968 | 43.102 | 107.704 |
| 2026 | 77.090 | 65.607 | 55.573 | 198.270 |

**Nguồn dữ liệu**
- 2023–2025 lấy từ [VietOnlineNews](https://huggingface.co/datasets/VLUS06/VietOnlineNews) trên Hugging Face, ghép với file metadata để có ngày đăng.
- 2026 do nhóm tự crawl.

## Các file

| File | Mỗi dòng là | Số dòng | Dung lượng | Tạo bởi |
|---|---|---:|---:|---|
| `articles_clean.parquet` | 1 bài (đầy đủ nội dung) | 463.995 | ~1,1 GB | notebook 04 |
| `article_events.parquet` | 1 bài → event được gán | 463.995 | ~53 MB | notebook 03 |
| `events.parquet` | 1 event | 320.842 | ~51 MB | notebook 03 |
| `events_config.json` | tham số đã dùng để gom event | — | — | notebook 03 |
| `coverage_daily.csv` | số bài theo ngày × nguồn | — | — | notebook 04 |
| `articles_clean_report.json` | thống kê quá trình làm sạch | — | — | notebook 04 |

Nối các file với nhau:
- `article_events.article_id` ↔ `articles_clean.article_id`
- `article_events.event_id` ↔ `events.event_id`

Đọc dữ liệu:
```python
import pandas as pd
a = pd.read_parquet("data/processed/article_events.parquet")
e = pd.read_parquet("data/processed/events.parquet")
```

## 1. `articles_clean.parquet`

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `article_id` | str | `sha256("{source}\|{url}")`, khoá chính |
| `source` | str | Thanh Niên / Tuổi Trẻ / VietnamNet |
| `origin` | str | `vietonlinenews` (2023–2025) hoặc `crawl_2026` |
| `url` | str | URL bài |
| `published_at` | str | Thời điểm đăng, dạng ISO có múi giờ +07:00 |
| `date` | date | Ngày đăng |
| `title`, `description`, `content` | str | Tiêu đề, sapo và nội dung, đã chuẩn hoá Unicode NFC |
| `category` | str | Chuyên mục, quy về 13 nhãn của VietOnlineNews. Thêm hai giá trị: `Khác` và `Không rõ` (toàn bộ bài Thanh Niên 2026) |
| `category_raw` | str | Chuyên mục gốc trên báo |
| `author`, `tags` | str | Tác giả và tag, có thể trống |
| `hf_id` | str | ID gốc trong VietOnlineNews (chỉ có ở 2023–2025) |
| `title_chars`, `content_words` | int | Độ dài tiêu đề (số ký tự) và nội dung (số từ) |
| `timezone_assumed` | bool | `True` nếu ngày gốc không có múi giờ và đã được giả định |
| `is_partial_day` | bool | Ngày mới crawl được một phần (07/11/2026). **Không dùng làm label** |

Các bước làm sạch:
- Bỏ bài thiếu tiêu đề, sapo hoặc nội dung.
- Bỏ trang video, podcast, ảnh.
- Bỏ bài dưới 78 từ.
- Bỏ bài trùng URL và bài trùng nội dung (548 bài).

## 2. `article_events.parquet`

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `article_id` | str | ID bài |
| `source` | str | Báo đăng bài |
| `published_at` | str | Thời điểm đăng (ISO) |
| `category` | str | Chuyên mục |
| `event_id` | str | **Event mà bài được gán vào**, ví dụ `E278678` |
| `decision` | str | Cách bài được gán, xem bảng dưới |
| `match_score` | float | Điểm giống với event ứng viên tốt nhất (0–1) |
| `best_candidate` | str | Event ứng viên tốt nhất, kể cả khi bài không được gán vào |
| `entities` | str (JSON) | Thực thể NER của bài, ví dụ `["kim sang sik", "mỹ đình"]` |

Các giá trị của `decision`:

| Giá trị | Số bài | Ý nghĩa |
|---|---:|---|
| `new` | 286.282 | Không giống event nào, mở event mới |
| `match` | 130.494 | Điểm ≥ 0,72, gán vào event cũ |
| `uncertain` | 34.560 | Điểm từ 0,65 đến dưới 0,72: vẫn gán vào event cũ nhưng độ tin cậy thấp |
| `routine` | 12.659 | Bài định kỳ (giá vàng, lịch âm, lịch thi đấu…), mỗi bài là một event riêng |

## 3. `events.parquet`

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `event_id` | str | ID event |
| `name` | str | Tên event: tiêu đề của bài gần tâm event nhất |
| `title` | str | Tiêu đề bài đầu tiên của event |
| `n_articles` | int | Tổng số bài |
| `n_sources`, `sources` | int, list | Số báo và danh sách báo đưa tin |
| `first_seen`, `last_seen` | str | Thời điểm bài đầu tiên và bài cuối cùng |
| `duration_days` | float | Số ngày event kéo dài, tối đa 14 |
| `category` | str | Chuyên mục chiếm đa số trong event |
| `entities` | list | Thực thể xuất hiện nhiều nhất trong event |

Ví dụ một số event lớn:
- "Đội tuyển Việt Nam … bị Singapore chia điểm": 284 bài
- "Lễ đón Tổng Bí thư … tại Singapore": 129 bài
- "Bất thường điểm 10 toán tại Tuyên Quang": 123 bài
- "Israel phát động cuộc tấn công mới vào Iran": 112 bài
- "Bão Kalmaegi hướng thẳng Gia Lai": 105 bài

## 4. `events_config.json`

Tham số đã dùng khi gom event:

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| Model embedding | `bkai-foundation-models/vietnamese-bi-encoder` | Mã hoá bài thành vector |
| NER | `underthesea` | Trích thực thể |
| `match_t` | 0,72 | Ngưỡng điểm để gán chắc chắn vào event cũ |
| `uncertain_t` | 0,65 | Ngưỡng điểm thấp nhất để vẫn gán vào event cũ |
| `max_gap_days` | 3 | Event không có bài mới quá 3 ngày thì đóng |
| `max_event_days` | 14 | Event kéo dài tối đa 14 ngày |
| `recent_k` | 5 | Số bài gần nhất của event dùng để so sánh |
| `centroid_weight` | 0,5 | Điểm giống = 0,5 × điểm so với tâm event + 0,5 × điểm cao nhất so với 5 bài gần nhất |
| `entity_weight` | 0,15 | Điểm cộng thêm nếu bài và event có chung thực thể |
| `entity_conflict_penalty` | 0 | Không trừ điểm khi thực thể khác nhau |

Ngưỡng `match_t` và `uncertain_t` là giá trị tạm. Chưa được kiểm chứng bằng dữ liệu gán nhãn tay (`data/annotation/`).

## Dùng cho các phase tiếp

| Phase | Lấy từ | Trường dùng |
|---|---|---|
| **4 – Thống kê event × ngày** | `article_events` | Gom nhóm theo `event_id` và ngày lấy từ `published_at` để có `article_count` mỗi ngày |
| **5 – Feature & label** | Bảng của Phase 4 | Feature tính từ 7 ngày trước: `article_count_7d`, tốc độ tăng, số ngày đã tồn tại… Label tính cho 3 ngày tới: `future_article_count_3d`, `is_emerging_next_3d` |
| 5 (tuỳ chọn) | `events`, `article_events` | Có thể dùng thêm `category`, `entities`, `match_score` làm feature |
| 8 – Dashboard | `events` | Hiển thị `name`, `entities` |

Phase 4 có thể bắt đầu như sau:
```python
a["date"] = a["published_at"].str[:10]
daily = a.groupby(["event_id", "date"]).size().rename("article_count").reset_index()
```

Ước lượng số event mới nổi:
- Định nghĩa thử: trong 3 ngày tới event có từ 10 bài trở lên, và gấp ít nhất 2 lần số bài của 7 ngày trước.
- Với định nghĩa này có khoảng **1.150 mẫu dương** (một mẫu = một cặp event × ngày), thuộc **670 event**. Một event có thể dương ở nhiều ngày liên tiếp.

## Lưu ý khi dùng

1. **Số bài mỗi ngày tăng mạnh theo thời gian.** Ví dụ, trung vị số bài mỗi ngày của Tuổi Trẻ:

   | 2023 | 2025 | 2026 |
   |---:|---:|---:|
   | 28 | 72 | 215 |

   Nên dùng feature tương đối (chuẩn hoá theo tổng số bài trong ngày) và đặt ngưỡng "mới nổi" theo percentile của từng năm.
2. **Tuổi Trẻ có 0 bài trong 13–15/05/2026** do crawl bị hụt. Nên bỏ các mẫu quanh những ngày này.
3. **Bóng đá bị gộp quá rộng.** Các event bóng đá lớn thường gộp cả một giải đấu. Có 701 event kéo dài đúng bằng giới hạn 14 ngày.
4. **Chuyên mục không nhất quán giữa hai giai đoạn.**
   - Thanh Niên 2026 không có chuyên mục (`Không rõ`).
   - Chuyên mục Pháp luật của VietnamNet 2026 có thể đang bị gộp vào Thời sự.
   - Cẩn thận khi dùng `category` làm feature.
5. **Chuyển sang ngày giờ khi dùng.** `published_at` đang là chuỗi. Dùng `pd.to_datetime(..., utc=True).dt.tz_convert("Asia/Ho_Chi_Minh")`.
