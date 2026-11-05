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
