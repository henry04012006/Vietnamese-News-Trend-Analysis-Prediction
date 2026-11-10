# Vietnamese News Trend Analysis & Prediction

> **Đề xuất dự án môn Data Science** · Nhóm 8 thành viên · Tài liệu định hướng để thảo luận và triển khai

## 1. Tổng quan dự án

Dự án xây dựng một pipeline Data Science để **thu thập tin tức tiếng Việt, phát hiện và theo dõi các sự kiện, phân tích diễn biến đưa tin theo thời gian, và dự đoán sự kiện nào có khả năng trở nên nổi bật trong 3 ngày tới**.

Hệ thống tập trung vào **những sự kiện đã xuất hiện trên báo**, không dự đoán sự kiện hoàn toàn mới chưa được nhắc đến.

Hai nhiệm vụ dự đoán dự kiến:

- **Classification:** Một sự kiện đã được ghi nhận nhưng hiện chưa nổi bật có khả năng trở thành *emerging trend* trong **3 ngày tiếp theo** hay không?
- **Regression:** Có bao nhiêu bài báo sẽ tiếp tục đưa tin về sự kiện đó trong **3 ngày tiếp theo**?

Mô hình dự đoán sử dụng thông tin có sẵn trong **7 ngày gần nhất (từ `t-6` đến `t`)**. Trong dự án này, *trend* được hiểu là **xu hướng mức độ đưa tin trên các trang báo được theo dõi**, không đồng nghĩa trực tiếp với lượt đọc, mức độ quan tâm của cộng đồng hay xu hướng mạng xã hội.

**Định hướng:** Đây là dự án **Data Science end-to-end**. Giá trị chính không chỉ nằm ở mô hình dự đoán mà còn ở chất lượng dữ liệu, cách tổ chức dữ liệu theo sự kiện và các phân tích rút ra từ dữ liệu.

## 2. Nguồn dữ liệu

| Nguồn | Giai đoạn | Nội dung |
| --- | --- | --- |
| [VietOnlineNews](https://huggingface.co/datasets/VLUS06/VietOnlineNews) | 2023–2025 | Khoảng **265.729 bài báo** từ **Tuổi Trẻ, Thanh Niên, VietnamNet**. |
| **Dữ liệu tự thu thập** | Từ 01/2026 trở đi | Backfill dữ liệu đầu năm 2026, sau đó crawl định kỳ từ **Tuổi Trẻ, Thanh Niên, VietnamNet, VnExpress**. |

Quy mô mục tiêu tham khảo: **300.000–400.000 bài báo** sau tích hợp; ưu tiên tính đầy đủ và chất lượng hơn số lượng tuyệt đối.

Một bản ghi bài báo dự kiến gồm:

`article_id`, `title`, `description`/`content`, `source`, `published_at`, `collected_at`, `url`, và metadata bổ sung nếu có.

**Lưu ý về độ phủ:** Dataset lịch sử chỉ có 3 nguồn, còn dữ liệu crawl dự kiến có thêm VnExpress. Các phân tích, thực nghiệm cần so sánh nhất quán theo thời gian nên ưu tiên bộ **3 nguồn chung**; VnExpress có thể được phân tích riêng hoặc đưa vào khi có dữ liệu lịch sử tương thích. Hoạt động crawl cần tuân thủ điều kiện truy cập, giới hạn tần suất và quyền sử dụng nội dung của từng nguồn.

## 3. Pipeline tổng thể

```text
Historical Dataset (2023–2025) + 2026 Backfill + Periodic Crawling
                              |
                              v
                 [1] Data Collection
                              |
                              v
            [2] Cleaning & Data Integration
                + Article-level Data Quality / EDA
                              |
                              v
             [3] Event Detection & Tracking
          Semantic Embedding + Entity + Time
                   Article -> Event ID
                              |
                              v
             [4] Event-level Data Analysis
            Event ID x Date -> Daily Statistics
                              |
                              v
           [5] Feature Engineering & Labeling
               Past 7 Days -> Next 3 Days
                              |
                              v
             [6] Trend Prediction (ML/DL)
           Classification + Article Count Forecast
                              |
                              v
                [7] Evaluation & Backtesting
                              |
                              v
              [8] Dashboard & Periodic Updates
```

## 4. Các giai đoạn triển khai

### Phase 1 — Data Collection

Tích hợp dataset lịch sử và dữ liệu crawl bổ sung. Với dữ liệu mới, ưu tiên những nguồn truy cập phù hợp như RSS, trang lưu trữ hoặc sitemap để thu thập bài báo theo lịch.

**Đầu ra:** Tập dữ liệu bài báo và metadata tương ứng.

### Phase 2 — Data Preprocessing & Article-level EDA

Làm sạch nội dung, chuẩn hóa thời gian và nguồn báo, loại bài trùng lặp, kiểm tra bài thiếu trường quan trọng và tích hợp các nguồn vào một cấu trúc thống nhất.

Thực hiện EDA ở mức bài báo: số lượng theo thời gian/nguồn, mức độ thiếu dữ liệu, tỷ lệ trùng lặp, các giai đoạn bị thiếu dữ liệu crawl. Cần phân biệt **không có bài báo** với **không thu thập được bài báo**.

**Đầu ra:** Dataset bài báo sạch, kèm báo cáo chất lượng và độ phủ dữ liệu.

### Phase 3 — Event Detection & Tracking (bước trọng tâm)

**Mục tiêu:** Từ các bài báo độc lập, xác định những bài đang nói về **cùng một sự kiện cụ thể** và duy trì mã sự kiện khi bài mới xuất hiện. *Cùng chủ đề* không nhất thiết là *cùng sự kiện*.

Ví dụ minh họa:

| Bài báo | Tiêu đề rút gọn | Event ID |
| --- | --- | --- |
| A001 | Bão Bualoi tiến vào Biển Đông | E001 |
| A002 | Miền Trung ứng phó bão số 10 | E001 |
| A003 | Bão Bualoi gây mưa lớn ở Nghệ An | E001 |
| A004 | Bão số 11 hình thành trên Biển Đông | E002 |
| A005 | Giá vàng SJC tăng mạnh | E003 |

#### Workflow dự kiến

1. **Biểu diễn nội dung:** Lấy `title` kết hợp `description`/`content` khi có; sử dụng **pretrained Vietnamese/multilingual embedding model** để tạo semantic vector cho bài báo.
2. **Trích xuất thực thể:** Sử dụng **NER (Named Entity Recognition)** để nhận diện người, tổ chức, địa điểm và các thực thể liên quan. Sau đó **Entity Matching/Resolution** để nhận biết những cách gọi khác nhau của cùng một đối tượng (nếu có đủ bằng chứng).
3. **Tìm event ứng viên:** Đối chiếu bài mới với các event đã phát hiện, ưu tiên các event có ngữ nghĩa gần và thời gian liên quan.
4. **Quyết định Match / New Event:** Kết hợp ba tín hiệu:
   - **Semantic similarity:** Nội dung có thực sự tương đồng?
   - **Entity consistency:** Có cùng người, địa điểm, tổ chức hoặc đối tượng sự kiện quan trọng không? Có mâu thuẫn thực thể nào không?
   - **Temporal constraints:** Thời điểm bài mới có phù hợp với diễn biến của event không?
5. **Cập nhật tracking:** Nếu match đủ tin cậy, thêm bài vào `event_id` hiện tại; nếu không phù hợp với event nào, tạo `event_id` mới. Trường hợp mơ hồ có thể giữ để kiểm tra, đồng thời cần cơ chế hiệu chỉnh/gộp event khi phát hiện nhóm sai.

```text
New Article
    |
    +--> Semantic Embedding
    +--> NER & Entity Resolution
    |
    v
Candidate Event Retrieval
    |
    v
Semantic + Entity + Time Matching
    |
    +--> Match    -> Assign existing event_id
    +--> New      -> Create new event_id
    +--> Uncertain -> Review / temporary handling
```

**Ví dụ:** Khi đã có `E001 = Bão Bualoi`, bài báo mới về diễn biến của chính cơn bão đó có thể được gán vào `E001`; bài về một cơn bão khác phải tạo nhóm riêng, dù cả hai có tiêu đề rất giống nhau.

**Phân biệt model và nhãn:** `event_id` là **mã định danh được hệ thống quản lý**, không phải lớp đầu ra cố định của một supervised classifier. Khi xuất hiện event mới, hệ thống có thể tự tạo `E004`, `E005`, ... mà không cần train lại model chỉ để thêm nhãn mới.

**Hướng kỹ thuật chính đã chọn:** **Semantic Embedding + Entity Matching + Time Constraints**. Tuy nhiên, embedding model, NER, thuật toán clustering/matching, cách biểu diễn event và các ngưỡng quyết định sẽ được **nghiên cứu và lựa chọn qua thực nghiệm**, chưa chốt cứng.

**Đánh giá Phase 3:** Dữ liệu nguồn chưa có nhãn sự kiện, nên nhóm dự kiến tạo **một tập ground truth nhỏ (ví dụ khoảng 500 bài, điều chỉnh theo thực tế)**. Các bài nói về cùng một sự kiện được người gán nhãn đặt cùng `event_id`; nhãn này **dùng để đánh giá/tuning**, không bắt buộc để train phương pháp unsupervised. Nên có tập development/test tách biệt và dùng các metric như **Pairwise Precision, Recall, F1**; đồng thời kiểm tra tracking bằng cách đưa bài báo vào theo trình tự thời gian.

**Đầu ra:** Bảng ánh xạ **`article_id -> event_id`**, thông tin cơ bản của từng event và lịch sử cập nhật event.

### Phase 4 — Event-level Data Analysis

Tổng hợp các bài đã được nhóm theo **`event_id × date`** thành bảng thống kê hằng ngày, ví dụ:

| event_id | date | article_count | source_count |
| --- | --- | ---: | ---: |
| E001 | 01/10 | 3 | 2 |
| E001 | 02/10 | 8 | 3 |
| E001 | 03/10 | 20 | 4 |

Thực hiện phân tích vòng đời sự kiện, tốc độ tăng/giảm số lượng bài báo, thời điểm đạt đỉnh, mức độ lan rộng giữa các nguồn báo và các đặc trưng có khả năng liên quan đến xu hướng nổi bật.

**Đầu ra:** Event-level dataset theo thời gian và những kết quả phân tích độc lập với mô hình dự đoán.

### Phase 5 — Feature Engineering & Prediction Labeling

Từ bảng event theo ngày, tạo training samples bằng **sliding window**. Mỗi sample tương ứng với **một event đã được biết tại thời điểm dự đoán `t`**.

| Thành phần | Khoảng thời gian | Nội dung |
| --- | --- | --- |
| **Input `X`** | `t-6` → `t` (7 ngày) | Số bài từng ngày, số nguồn báo, tốc độ tăng trưởng, tuổi event, các đặc trưng thời gian; có thể thêm semantic features từ bài đã xuất hiện. |
| **Label hồi quy** | `t+1` → `t+3` | Tổng số bài báo thực tế về event trong 3 ngày tiếp theo (`future_article_count_3d`). |
| **Label phân loại** | `t+1` → `t+3` | Event hiện chưa nổi bật có trở thành *emerging trend* trong 3 ngày tới không (`is_emerging_next_3d`). |

**Lưu ý về hai loại nhãn:** `event_id` của Phase 3 phục vụ **nhóm và theo dõi sự kiện**; `is_emerging_next_3d` và `future_article_count_3d` của Phase 5 mới là **target để train prediction model**.

Định nghĩa chính xác *emerging trend* (mức tăng, số lượng bài tối thiểu, số nguồn báo, điều kiện event chưa hot tại `t`) **chưa chốt**. Nhóm sẽ xây định nghĩa dựa trên EDA và thực nghiệm, tránh đặt ngưỡng tùy ý rồi coi là chuẩn.

Những event mới xuất hiện chưa đủ 7 ngày cần được xử lý nhất quán (ví dụ padding/mask và tuổi event); lựa chọn cụ thể sẽ được quyết định khi khảo sát dữ liệu.

**Đầu ra:** Training dataset gồm `X` và các nhãn dự đoán cho từng `event_id`, thời điểm `t`.

### Phase 6 — Trend Prediction

Xây dựng và so sánh các nhóm phương pháp:

- **Baseline:** Dự đoán đơn giản dựa vào mức độ đưa tin và xu hướng tăng trưởng hiện tại.
- **Machine Learning:** Có thể thử XGBoost/LightGBM với temporal features.
- **Deep Learning / Hybrid (nếu phù hợp):** Có thể thử GRU/LSTM, hoặc kết hợp temporal features với embedding ngữ nghĩa của event.

Không mặc định deep learning tốt hơn. Mục tiêu là đánh giá **những đặc trưng và phương pháp nào thực sự giúp dự đoán tốt hơn**, nhất là việc bổ sung thông tin văn bản so với chỉ dùng số lượng bài.

### Phase 7 — Evaluation & Backtesting

Đánh giá cả **Event Detection & Tracking** lẫn **Trend Prediction**:

| Thành phần | Hướng đánh giá |
| --- | --- |
| Event Clustering/Tracking | Ground truth nhỏ được kiểm tra thủ công; Pairwise Precision/Recall/F1; kiểm tra bài mới có được gán đúng event. |
| Emerging Classification | PR-AUC, F1, Precision@K / Recall@K (tùy mục tiêu sử dụng). |
| Article Count Regression | MAE, RMSE và so sánh với baseline. |

Sử dụng **chia train/validation/test theo thời gian** và **rolling backtesting**. Tại thời điểm dự đoán `t`, toàn bộ features và trạng thái event tracking chỉ được dựa trên thông tin đã có đến `t`; dữ liệu của `t+1` → `t+3` chỉ dùng tạo ground truth. Cần kiểm soát các sliding windows có target chồng lấn và sự khác biệt về độ phủ nguồn tin.

### Phase 8 — Dashboard & Periodic Updates

Xây dựng dashboard (ví dụ bằng Streamlit/Plotly) để thể hiện:

- Những event đang được ghi nhận và các bài báo liên quan.
- Biểu đồ số lượng bài theo ngày, mức tăng trưởng và phân bố theo nguồn báo.
- Xác suất một event trở thành *emerging trend* trong 3 ngày tiếp theo.
- Số bài báo dự kiến xuất hiện trong 3 ngày tiếp theo.

Pipeline cập nhật định kỳ: **crawl bài mới → preprocessing → cập nhật event tracking → cập nhật event features → chạy prediction model đã train → cập nhật dashboard**. Không cần train lại prediction model sau mỗi lần crawl.

## 5. Những vấn đề cần tiếp tục nghiên cứu và thống nhất

Các mục dưới đây **cố ý chưa chốt**, để nhóm kiểm chứng trên dữ liệu trước khi quyết định:

1. **Event Detection & Tracking:** Chọn embedding/NER, thuật toán matching/clustering, cách đánh giá entity/time, ngưỡng Match/New và cách xử lý event mơ hồ hoặc trùng nhóm.
2. **Ground truth:** Quy mô và cách chọn mẫu gán nhãn thủ công; quy tắc xác định *cùng sự kiện*; quy trình kiểm tra độ nhất quán khi gán nhãn.
3. **Emerging trend definition:** Tiêu chí đủ nổi bật, đủ mới và thời hạn áp dụng; cách cân bằng giữa event ngắn hạn và event kéo dài.
4. **Data coverage:** Khả năng backfill 2026, sự đầy đủ của từng nguồn và cách kiểm soát chênh lệch giữa bộ 3 nguồn và 4 nguồn.
5. **Prediction experiments:** Bộ features, baseline, ML/DL models, protocol backtesting và các metric phù hợp với mục tiêu dashboard.

## 6. Kết quả dự kiến

- **Dataset bài báo đã xử lý** và thống kê chất lượng/độ phủ.
- **Event detection & tracking pipeline** cùng kết quả đánh giá trên tập gán nhãn nhỏ.
- **Event-level time-series dataset** và phần **EDA/temporal analysis**.
- **Training samples và prediction labels**, kèm mô tả cách định nghĩa target.
- **Baseline và các mô hình dự đoán** được so sánh bằng backtesting.
- **Dashboard/demo** theo dõi sự kiện và hiển thị dự đoán cập nhật định kỳ.

## 7. Nguồn tham khảo ban đầu

**Dữ liệu và event detection/tracking**

- [VietOnlineNews — Hugging Face Dataset](https://huggingface.co/datasets/VLUS06/VietOnlineNews)
- [NewsTrace — News Story Evolution Tracker](https://github.com/teenatom17/NewsTrace)
- [news-clustering — Story Clustering & Tracking](https://github.com/sidcmenon/news-clustering)
- [ContextNews/news-pipeline](https://github.com/ContextNews/news-pipeline)
- [Underthesea — Vietnamese NLP/NER](https://github.com/undertheseanlp/underthesea)
- [Event-Driven News Stream Clustering using Entity-Aware Contextual Embeddings (EACL 2021)](https://aclanthology.org/2021.eacl-main.198/)

**Dự đoán chuỗi thời gian**

- [MLForecast](https://github.com/Nixtla/mlforecast)
- [NeuralForecast](https://github.com/Nixtla/neuralforecast)

> **Ghi chú:** Các repo/paper trên là nguồn nghiên cứu, không phải danh sách công nghệ bắt buộc. Nhóm sẽ lựa chọn phương pháp cụ thể sau khi kiểm tra dữ liệu và đánh giá thực nghiệm.

## 8. Crawler Tuổi Trẻ — chạy mẫu trước

Yêu cầu Python 3.11+. Cài dependency và kiểm tra:

```powershell
python -m pip install -r requirements-crawl.txt
python -m pytest -q
python crawl_tuoitre.py category-sample --config config/tuoitre.json
```

Thông số nằm trong `config/tuoitre.json`: nguồn/sitemap, thời gian, selectors,
schema, quy tắc URL/ID, delay, timeout, retry, tên file và tiêu chí kiểm tra.
`categories` chứa đúng 18 tên/URL chuyên mục được yêu cầu. Chế độ `category-sample`
đọc từng trang, chọn tối đa `category_sample.max_candidates` URL ứng viên (mặc định 6),
dừng khi có `category_sample.per_category` bài hợp lệ mỗi nhóm (mặc định 2).
Danh sách ứng viên được lưu cố định để resume. Nếu muốn đổi danh sách hoặc lấy mẫu mới,
dùng thư mục `output.directory` mới trong bản config riêng.

`category` lấy từ chuyên mục chính trong breadcrumb, rồi fallback `article:section`;
tên/aliases chuẩn hóa theo config. Không dùng mô hình phân loại nội dung. Bài được
giới thiệu ở nhiều trang vẫn giữ category chính thức của trang bài. Nếu không khớp nhóm
đang lấy mẫu, ghi log và thử ứng viên tiếp theo; không gán lại nhãn để đủ quota.

Video được nhận diện bằng đường dẫn `/video/`. Nếu thân bài không có text, `content`
dùng mô tả do Tuổi Trẻ đăng; không tải video hoặc tạo transcript. Trường hợp không có
category thuộc danh sách hoặc thiếu text sẽ được ghi lỗi.

Chế độ mẫu theo thời gian vẫn có thể chạy riêng:

```powershell
python crawl_tuoitre.py sample --config config/tuoitre.json
```

Chế độ này chọn 20 URL từ sitemap mới nhất và 10 URL trải đều trong sitemap đầu năm;
không bảo đảm đủ 18 chuyên mục.

Đầu ra trong `data/tuoitre/` (được `.gitignore` bỏ qua):

- `sample_tuoitre_categories.csv`: mẫu mới đủ 18 chuyên mục, UTF-8 BOM.
- `category-sample_urls.json`: các URL ứng viên cùng trang/chuyên mục nguồn và URL cuối nếu có redirect.
- `category-sample_report.json`: số hợp lệ theo từng category, quota còn thiếu và kiểm tra chất lượng.
- `category-sample_errors.jsonl`: URL lỗi/lệch chuyên mục theo từng lần thử.
- `category_sample_html/`: HTML gốc của các bài trong mẫu chuyên mục.
- `sample_tuoitre.csv`: bài hợp lệ, UTF-8 BOM để mở tiếng Việt trong Excel; giữ xuống dòng trong content.
- `sample_urls.json`: 30 URL thử, nhóm mới/cũ, sitemap và URL sau redirect nếu có.
- `sample_report.json`: số bài, lỗi, trường thiếu, trùng lặp, phạm vi thời gian và kết quả kiểm tra tự động. `attempted`/`saved` là số của lượt chạy hiện tại; `total_valid` là tổng trong CSV.
- `sample_errors.jsonl`: lịch sử lỗi theo từng lần thử; một URL có thể xuất hiện nhiều lần.
- `sample_html/`: HTML gốc của bài hợp lệ để đối chiếu.

Ngày đăng lấy từ `datePublished` (fallback `article:published_time`), yêu cầu timezone;
không dùng ngày sửa hoặc ngày crawl thay thế. Nội dung bỏ ảnh/chú thích ảnh, quảng cáo
và hộp tin liên quan. Layout không có tiêu đề/thân bài phù hợp sẽ được ghi lỗi.
`description` có thể trống; `category` là trường bắt buộc. Bài dưới ngưỡng độ dài chỉ gắn cờ.

Kết quả mẫu chuyên mục ngày 07/11/2026: **36 bài, 18 nhóm × 2 bài**, từ 40 lượt thử
trong 108 URL ứng viên. Không thiếu category hoặc trùng URL/ID; có 4 trường hợp lỗi/lệch nhóm
được ghi log. Xem [báo cáo chuyên mục](docs/tuoitre_category_sample_review.md).

Mẫu theo thời gian trước đó có **29/30 URL hợp lệ** (19 mới, 10 đầu năm), xem
[đối chiếu mẫu cũ](docs/tuoitre_sample_review.md). CSV cũ đã được bổ sung category từ HTML
đã lưu, giữ nguyên các trường còn lại; bản trước cập nhật nằm trong `sample_tuoitre_before_categories.csv`.
Trong mẫu cũ có 3 bài ngoài danh sách 18 nhóm: `Cần biết` và `Tin tức thị trường`;
giữ nguyên nhãn nguồn để đối chiếu, không ép sang nhóm khác.
Mẫu này chưa chứng minh độ phủ toàn bộ website hoặc mọi dạng bài.

### Backfill sau khi kiểm tra mẫu

**Đã được yêu cầu tiếp tục theo từng tháng, từ 01/01/2026 đến 07/11/2026.** Hàng đợi
đang resume tháng 1 và sẽ tự chuyển tuần tự sang tháng sau:

```powershell
python crawl_tuoitre_monthly.py --config config/tuoitre.fast.json
```

Xem [hướng dẫn crawl theo tháng](docs/tuoitre_monthly_crawl.md). Không khởi chạy lệnh này
lần nữa khi hàng đợi hiện tại còn chạy. Các tháng chưa hoàn thành vẫn được đánh dấu pending;
không coi việc tạo hàng đợi là đã crawl xong dữ liệu.

Nếu chỉ cần chạy/resume riêng tháng 1, config kế thừa chính sách chung từ `tuoitre.json`:

```powershell
python crawl_tuoitre.py backfill --config config/tuoitre.january2026.json
```

Không chạy thêm một writer cùng thư mục. Xem
[bằng chứng resume pilot](docs/tuoitre_january_pilot.md).
Lệnh core cho một khoảng ngày riêng trong config là:

```powershell
python crawl_tuoitre.py backfill --config config/tuoitre.json
```

Lệnh này không tự chạy sau sample. Nó đọc sitemap trong khoảng config, kiểm tra ngày đăng
thực tế và lưu vào `tuoitre_YYYY-MM.csv` theo tháng đăng, từ 01/01/2026 đến ngày chạy
(hoặc `end_date` nếu được đặt). `sitemap_lookback_months` cho phép nhìn lùi tháng trước;
chỉ đọc kỳ có ngày kết thúc cộng `sitemap_boundary_overlap_days` giao với khoảng yêu cầu.
Ngày đăng thực tế ngoài khoảng được ghi `outside_range` và không lưu. Đây là CLI để backfill/cập nhật thủ công,
chưa có scheduler. Có thể thử một tháng bằng bản config riêng với `start_date`/`end_date`
và thư mục đầu ra riêng trước khi chạy hết.

Backfill lịch sử dùng sitemap để tìm URL, sau đó đọc category chính thức của từng bài
và chỉ nhận các nhóm trong config. Hai chế độ mẫu không chứng minh độ phủ lịch sử;
trang đầu của 18 chuyên mục không được coi là toàn bộ bài từ đầu năm. `additional_sitemap_indexes`
bổ sung index Video lịch sử. Đã đọc được các kỳ năm 2026 và kiểm tra một Video tháng 1;
độ phủ toàn tháng/năm vẫn phải đánh giá sau crawl.

Nhãn con đọc từ breadcrumb HTML hoặc `BreadcrumbList` JSON-LD. `category_routes` ánh xạ
nhánh `/chung-khoan/` về Kinh doanh theo cấu trúc nguồn; bài “Tin tức thị trường” vì thế
không bị loại chỉ vì nhãn con. `excluded_categories` liệt kê những nhánh ngoài 18 nhóm
đã xác minh (Cần biết, Thư giãn, Thời tiết); các category không nhận diện khác vẫn là lỗi
cần xem lại, không tự suy đoán từ nội dung.

Config gốc tải tuần tự, cách nhau tối thiểu **1 giây** giữa các lần bắt đầu request. Hàng đợi
hiện dùng `tuoitre.fast.json`: **3 worker**, prefetch **6**, khoảng cách chung **0,25 giây**
(tối đa 4 lượt bắt đầu request/giây cho toàn bộ worker). Nếu robots quy định crawl-delay
lớn hơn thì dùng giá trị lớn hơn. Timeout/5xx
retry giới hạn. Robots từ chối hoặc HTTP 401/403/429 sẽ dừng toàn lượt chạy.
Mỗi bài được ghi CSV ngay; RAM chỉ giữ các trường metadata trong `output.backfill_memory_fields`
và cờ chất lượng. `output.csv_field_limit` cấu hình giới hạn đọc trường CSV dài.
`backfill_urls.json` đóng băng manifest và khoảng ngày; chạy lại cùng output phải dùng cùng
khoảng ngày. `backfill_results.jsonl` lưu kết quả cuối theo requested URL cùng URL sau redirect.
Chạy lại bỏ qua bản ghi đã lưu, các URL đã xác định ngoài scope/ngày; URL lỗi được retry
theo `backfill.retry_errors_on_resume`. `backfill.max_attempts_per_run` cho phép giới hạn
lượt thử để kiểm tra checkpoint (`null` để chạy hết manifest).

Report cập nhật sau mỗi `progress_every` lượt và khi kết thúc. `attempted`/`saved`/`errors`
là số của lượt hiện tại; `total_valid`, `result_counts`, `unresolved_urls`, `pending_count`
phản ánh dữ liệu/journal tích lũy. Có `valid_by_day`, `valid_by_category`, `zero_record_days`;
ngày 0 bản ghi không chứng minh ngày đó không có bài báo.

Status: `running` đang chạy; `checkpointed` dừng theo giới hạn config; `interrupted` bị Ctrl+C;
`stopped` lỗi chặn/mạng nghiêm trọng; `finished` hết manifest không còn URL lỗi;
`finished_with_errors` hết manifest nhưng còn URL lỗi cần xử lý. Hai trạng thái cuối vẫn
không chứng minh đã thu thập đủ toàn bộ website. Lỗi từng bài không ngăn lấy bài tiếp theo;
xem cả `backfill_report.json`, `backfill_errors.jsonl` và `backfill_results.jsonl`.

Không chạy hai tiến trình cùng thư mục đầu ra. Ctrl+C giữ CSV đã ghi; nếu tiến trình bị
kill đột ngột để lại `.crawl.lock`, chỉ xóa khóa sau khi xác nhận không còn crawler đang chạy.
Không ghi đè dataset đã chốt; dùng một thư mục output mới cho phiên bản mới.

### Tối ưu tốc độ

Benchmark mới ngày 07/11/2026: **3.509 → 9.657 URL/giờ**, nhanh hơn **2,75 lần** so với
mức tuần tự 1 giây. Đợt thử 3 worker xử lý 100 URL trong 37,28 giây, lưu 94 bài; không có
HTTP chặn, không trùng/thiếu trường bắt buộc, phần CSV cũ và manifest giữ nguyên.
Chỉ luồng chính parse và ghi CSV; mỗi worker có HTTP session riêng, queue tải trước hữu hạn.
Xem [báo cáo tăng tốc song song](docs/tuoitre_rapid_speed.md) và
[benchmark trước đó](docs/tuoitre_speed_optimization.md).

`date_cache` đọc metadata ngày đăng đã xác minh từ journal các tháng khác. Chỉ bỏ request
khi biết chắc ngày đó nằm ngoài tháng đang lấy; vẫn tải body nếu ngày thuộc tháng hiện tại.
Metadata mâu thuẫn hoặc thiếu timezone không được dùng để skip. Journal nguồn chỉ được đọc.
`date_cache_skips` trong report đo số request tránh được trong lượt hiện tại; lợi ích thực tế
của cache sẽ xuất hiện khi đi qua các tháng tiếp theo.

Hàng đợi đã resume lúc 20:30 với `config/tuoitre.fast.json`; không chạy thêm writer. Cấu hình benchmark hữu hạn
`config/tuoitre.speedtest.json` chỉ dành cho kiểm tra 100 lượt khi hàng đợi đã dừng có checkpoint.
