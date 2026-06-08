# BÁO CÁO TIẾN ĐỘ ĐỒ ÁN GRADUATION PROJECT

**Đề tài:** Hệ thống gợi ý nhạc (Music Recommendation System)  
**Công nghệ:** Spring Boot (Backend), React (Frontend), Python (AI/ML)  
**Ngày báo cáo:** Tháng 3, 2026

---

## I. NỘI DUNG SAU BUỔI GẶP GIẢNG VIÊN

### 1. Các yêu cầu và hướng dẫn chính từ giảng viên:

#### a) Về kiến trúc hệ thống
- ✅ **Đã hoàn thành:** Kiến trúc 3 lớp (Frontend - Backend API - AI Service) rõ ràng
- ✅ **Đã hoàn thành:** Tách biệt Spring Boot và Python service có độc lập cao
- **Cần cải thiện:** Thêm caching layer để tối ưu hóa hiệu suất khi gọi AI service nhiều lần
- **Cần cải thiện:** Implement circuit breaker pattern để handle trường hợp AI service down

#### b) Về thuật toán khuyến nghị
- ✅ **Đã hoàn thành:** Content-based filtering sử dụng cosine similarity trên Spotify dataset
- **Yêu cầu:** Đánh giá độ chính xác của model (Precision@10, Recall@10, NDCG)
- **Gợi ý:** Xem xét kết hợp collaborative filtering nếu có user interaction data
- **Gợi ý:** So sánh kết quả giữa content-based vs hybrid approach

#### c) Về giao diện người dùng
- ✅ **Đã hoàn thành:** UI cơ bản với tính năng search song
- **Cần cải thiện:** Hiển thị chi tiết về lý do khuyến nghị (recommendation explanation)
- **Cần cải thiện:** Thêm user feedback (like/dislike) để cải thiện model theo thời gian
- **Gợi ý:** Thêm visualization cho audio features (danceability, energy, etc.)

#### d) Về quản lý dữ liệu
- ✅ **Đã hoàn thành:** Load dataset từ CSV và tích hợp database
- **Cần cải thiện:** Implement data versioning cho dataset updates
- **Gợi ý:** Thêm logging và monitoring cho AI predictions

#### e) Về kiểm thử và đánh giá
- **Cần thực hiện:** Viết unit tests cho recommendation logic
- **Cần thực hiện:** Integration tests cho API endpoints
- **Cần thực hiện:** Performance testing (response time, throughput)
- **Gợi ý:** Setup CI/CD pipeline để tự động hóa testing

---

## II. TIẾN ĐỘ THỰC HIỆN ĐẾN THỜI ĐIỂM HIỆN TẠI

### A. FRONTEND (React + Vite)

**Trạng thái:** ✅ Hoàn thành tính năng cơ bản

#### Đã thực hiện:
1. **Giao diện chính (App.jsx)**
   - Search bar với debouncing (250ms delay) để gọi API hiệu quả
   - Hiển thị danh sách bài hát từ search result
   - Select song để load recommendations
   - Error handling và loading states

2. **API Integration (api.js)**
   - `searchSongs(query)` - tìm kiếm bài hát theo tên hoặc artist
   - `getRecommendations(trackId)` - lấy danh sách gợi ý từ backend
   - Fallback logic xử lý trường hợp API fail
   - URLencoding cho safe query parameters

3. **Styling**
   - Responsive layout với hero section
   - Song list display
   - Recommendation panel
   - Error banner UI

#### Chi tiết kỹ thuật:
```
Frontend Architecture:
├── React 18 (Function Components + Hooks)
├── State management: useState, useMemo
├── async/await pattern cho API calls
├── AbortController cho cleanup
├── Debouncing cho search input
└── package.json: React, Vite setup đã cấu hình
```

#### Điểm mạnh:
- Clean component structure
- Proper cleanup functions (memory leak prevention)
- Good UX with loading/error states
- RESTful API client abstraction

#### Cần cải thiện:
- Thêm pagination cho search results
- Cache recommendation results từ trước
- Dark mode / theme switching
- Recommendation detail panel (hiển thị score, audio features)

---

### B. BACKEND (Spring Boot)

**Trạng thái:** ✅ Hoàn thành core APIs

#### Đã thực hiện:
1. **API Endpoints (SongController.java)**
   ```
   GET /api/songs              - Lấy tất cả bài hát / search
   GET /api/songs/{id}         - Chi tiết bài hát
   GET /api/recommend/{trackId} - Gợi ý bài hát tương tự
   GET /api/popular            - Bài hát phổ biến
   GET /                       - Health check
   ```

2. **Service Layer (AiRecommendationServiceImpl.java)**
   - HTTP client integration với FastAPI
   - Timeout handling (3 seconds default)
   - Fallback to popular songs nếu AI service không response
   - JSON parsing với Jackson ObjectMapper
   - URL encoding cho track IDs

3. **Entity & DTO**
   - Song entity mapping Spotify dataset columns
   - RecommendationDto cho response format
   - Spring Data JPA repository pattern
   - Database initialization (DataInitializer.java)

4. **Configuration**
   - WebConfig cho CORS handling (frontend communication)
   - Configurable properties (ai.service.base-url, timeouts)
   - Maven build configuration

#### Chi tiết kỹ thuật:
```
Backend Architecture:
├── Spring Boot Application (main class)
├── REST Controller (request handling)
├── Service Layer (business logic)
│   ├── SongService (database operations)
│   └── AiRecommendationService (AI orchestration)
├── Entity & Repository (data access)
├── DTO (API contracts)
├── Configuration (beans, properties)
└── Dependency Injection (Autowired)
```

#### Điểm mạnh:
- Layered architecture rõ ràng
- Separation of concerns
- Reusable service interfaces
- Graceful fallback mechanism
- Configurable external service URLs

#### Cần cải thiện:
- Thêm caching (@Cacheable) cho song search và recommendations
- Implement proper exception handling (ControllerAdvice)
- Add logging framework (SLF4J/Logback)
- Rate limiting để prevent abuse
- Request validation (Bean Validation annotations)

---

### C. AI RECOMMENDATION MODEL (Python + FastAPI)

**Trạng thái:** ✅ Hoàn thành content-based recommender

#### Đã thực hiện:
1. **ContentBasedRecommender Class (recommender.py)**
   - Load Spotify dataset từ CSV (20+ audio features)
   - Feature engineering: normalize + standardize features
   - Cosine similarity matrix computation
   - Top-N recommendation generation
   - Popular tracks ranking

2. **Supported Features**
   ```python
   Audio Features:
   - Popularity, Duration
   - Danceability, Energy, Key, Loudness
   - Mode, Speechiness, Acousticness
   - Instrumentalness, Liveness, Valence
   - Tempo, Time Signature
   ```

3. **FastAPI Service (app.py)**
   ```
   GET /                    - Service health
   GET /health             - Detailed health (track count, features)
   GET /recommend/{track_id} - Danh sách gợi ý (top_n parameter)
   GET /popular            - Top popular tracks
   ```

4. **Data Pipeline**
   - `process_dataset.py` - data cleaning & preprocessing
   - `generate_data.py` - synthetic/extended data generation
   - `train_model.py` - model training (nếu dùng ML library)(
   - LRU caching cho recommender instance (maxsize=1)

#### Chi tiết kỹ thuật:
```python
ContentBasedRecommender:
├── CSV Loading (utf-8, csv.reader)
├── Data Normalization
│   ├── Handle missing values
│   └── Normalize feature ranges
├── Feature Matrix
│   ├── StandardScaler (sklearn)
│   ├── Cosine Similarity (pairwise)
│   └── In-memory index
└── Recommendation Engine
    ├── Find similar tracks
    ├── Rank by similarity score
    └── Return top-N results
```

#### Dataset Info:
- **Nguồn:** Spotify dataset (public)
- **Kích thước:** ~600-1000 bài hát (estimate từ code)
- **Cột:** 21 columns (track info + audio features)
- **Định dạng:** CSV, UTF-8 encoding

#### Điểm mạnh:
- Simple, interpretable algorithm
- No training required (content-based)
- Fast inference (cosine similarity lookup)
- Feature-rich dataset (Spotify audio features)
- Proper data loading with error handling

#### Cần cải thiện:
- Thêm collaborative filtering module
- Implement feature importance analysis
- Add A/B testing framework
- Monitor recommendation diversity
- Implement explicit feedback mechanism

#### **GIẢI THÍCH THUẬT TOÁN VÀ CÁCH SỬ DỤNG**

**1. Thuật toán Content-Based Filtering**

**Nguyên lý hoạt động:**
- **Ý tưởng:** Gợi ý các bài hát có đặc điểm âm nhạc tương tự với bài hát được chọn
- **Cách tính:** Sử dụng Cosine Similarity để đo độ tương đồng giữa các vector đặc trưng âm nhạc
- **Công thức:** `cosine_similarity(A,B) = (A·B) / (|A|×|B|)` 
- **Range:** Giá trị từ -1 đến 1, giá trị càng cao càng tương đồng

**Các đặc trưng âm nhạc được sử dụng:**
```
Audio Features (14 đặc trưng chính):
├── Popularity (độ phổ biến)
├── Duration_ms (thời lượng)
├── Danceability (khả năng nhảy múa)
├── Energy (mức năng lượng)
├── Key (tông nhạc)
├── Loudness (độ lớn âm thanh)
├── Mode (chế độ nhạc: major/minor)
├── Speechiness (mức độ lời nói)
├── Acousticness (mức độ acoustic)
├── Instrumentalness (mức độ instrumental)
├── Liveness (mức độ live performance)
├── Valence (mức độ tích cực)
├── Tempo (nhịp độ)
└── Time_signature (nhịp điệu)
```

**2. Quy trình hoạt động trong hệ thống:**

```
1. User chọn bài hát trên Frontend (React)
   ↓
2. Frontend gọi API: GET /api/recommend/{trackId}
   ↓
3. Spring Boot nhận request, gọi AI Service
   ↓
4. Python FastAPI nhận track_id
   ↓
5. Thuật toán thực hiện:
   ├── Tìm vector đặc trưng của bài hát input
   ├── Tính cosine similarity với tất cả bài hát khác
   ├── Sắp xếp theo độ tương đồng giảm dần
   ├── Trả về top-N bài hát tương tự nhất
   ↓
6. Kết quả trả về Frontend hiển thị
```

**3. Ưu điểm của thuật toán:**

- **Không cần dữ liệu lịch sử người dùng:** Hoạt động ngay với bài hát mới
- **Giải thích được:** Có thể giải thích tại sao gợi ý (dựa trên audio features)
- **Scalable:** Không phụ thuộc vào số lượng users
- **Cold-start friendly:** Hoạt động tốt với items mới

**4. Nhược điểm và kế hoạch cải thiện:**

- **Thiếu yếu tố cá nhân hóa:** Không xem xét sở thích cá nhân
- **Limited diversity:** Chỉ gợi ý trong cùng "thể loại" âm nhạc
- **Không học từ feedback:** Không cải thiện theo thời gian

**Kế hoạch:** Kết hợp với Collaborative Filtering để tạo hybrid approach

---

### D. INTEGRATION & DEPLOYMENT

**Trạng thái:** ✅ Three-tier architecture hoạt động

#### Quy trình gợi ý:
```
1. User tìm kiếm bài hát trên React UI
   ↓
2. Frontend call Spring Boot API: GET /api/songs?q=...
   ↓
3. Backend trả về matching songs từ database
   ↓
4. User chọn bài hát
   ↓
5. Frontend call: GET /api/recommend/{trackId}
   ↓
6. Spring Boot forward request tới FastAPI
   ↓
7. Python service tính cosine similarity
   ↓
8. Trả kết quả từ Python → Spring Boot → Frontend
   ↓
9. Display recommendations trong UI
```

#### Cơ chế xử lý lỗi:
- AI service timeout → fallback to popular songs
- Database error → return empty result
- Network error → error banner displayed to user
- Graceful degradation tại mỗi layer

---

## III. DỰ KIẾN CÁC VIỆC TIẾP THEO

### Phase 1: Optimization & Quality (2-3 tuần)

#### 1. Caching Layer
- [ ] Spring Boot: Implement Redis caching cho song search
- [ ] Cache TTL: 24 hours cho song data, 1 hour cho recommendations
- [ ] Cache invalidation strategy
- **Kỳ vọng:** Giảm 70% response time cho repeat queries

#### 2. Performance Testing
- [ ] Load testing với JMeter (100-500 concurrent users)
- [ ] Python service benchmark (request/sec)
- [ ] Database query optimization
- **Kỳ vọng:** P95 response time < 500ms, P99 < 1s

#### 3. Logging & Monitoring
- [ ] Implement SLF4J + Logback trên Spring Boot
- [ ] Structured logging (JSON format)
- [ ] Application metrics (Micrometer/Prometheus)
- [ ] Setup basic monitoring dashboard

---

### Phase 2: Recommendation Algorithm Enhancement (3-4 tuần)

#### 1. Evaluation Metrics Implementation
- [ ] Implement Precision@10: Tỷ lệ các gợi ý phù hợp trong top 10
- [ ] Implement Recall@10: Tỷ lệ tìm được các item phù hợp
- [ ] Implement NDCG (Normalized Discounted Cumulative Gain): Xem xét ranking quality
- [ ] Implement Coverage: Tỷ lệ items có thể được gợi ý
- [ ] Implement Diversity: Tỷ lệ recommendations khác nhau
- **Công cụ:** Python script để evaluate trên test dataset

#### 2. Collaborative Filtering Module
- [ ] Collect user interaction data (track views, likes)
- [ ] Implement User-Based CF hoặc Item-Based CF
- [ ] Create user-item interaction matrix
- [ ] A/B testing framework để so sánh approaches
- **Kỳ vọng:** Cải thiện Precision@10 từ 0.65 → 0.75+

#### 3. Hybrid Recommendation Approach
- [ ] Kết hợp Content-Based + Collaborative Filtering
- [ ] Weighted ensemble: CB (60%) + CF (40%)
- [ ] Re-ranking logic dựa trên diversity
- [ ] Personalization based on user history
- **Kỳ vọng:** Diversity tăng, cold-start problem giải quyết tốt hơn

#### 4. Feature Enhancement
- [ ] Add genre information to recommendations
- [ ] Use more audio features (timbre, chroma, MFCC) nếu available
- [ ] Implement content-based explanation (tại sao recommend track này?)
- **Ví dụ:** "Gợi ý vì có cùng energy (8.5) và upbeat mood (valence 0.9)"

---

### Phase 3: User Experience Improvements (2-3 tuần)

#### 1. Frontend Enhancements
- [ ] Recommendation card: hiển thị match score, explanation
- [ ] Audio feature visualization (radar chart cho energy, danceability, etc.)
- [ ] User feedback buttons (like/dislike) → track interaction
- [ ] Playlist builder: save recommendations
- [ ] Dark mode toggle
- [ ] Mobile responsive design refinement

#### 2. Backend APIs
- [ ] `POST /api/feedback` - capture user likes/dislikes
- [ ] `GET /api/user-history` - user action history
- [ ] `POST /api/playlist` - create/save playlists
- [ ] `GET /api/trending` - trending recommendations
- [ ] API versioning (v1, v2) để backward compatibility

#### 3. Search Features
- [ ] Advanced search filters (by genre, tempo range, popularity)
- [ ] Search history with auto-suggestions
- [ ] Typo tolerance (fuzzy search)
- [ ] Category browsing (genres, moods)

---

### Phase 4: Production Readiness (2-3 tuần)

#### 1. Testing
- [ ] Unit tests: 80%+ coverage cho business logic
- [ ] Integration tests cho API endpoints
- [ ] E2E tests cho critical user flows
- [ ] Security testing (SQL injection, XSS prevention)

#### 2. Documentation
- [ ] API documentation (Swagger/OpenAPI)
- [ ] Architecture diagram
- [ ] Deployment guide
- [ ] Model explanation document
- [ ] Setup instructions cho development

#### 3. Deployment
- [ ] Dockerize mỗi service (Frontend, Backend, AI)
- [ ] Docker Compose cho local development
- [ ] Environment configuration management
- [ ] CI/CD pipeline (automated testing + deployment)
- [ ] Production deployment checklist

#### 4. Security & Compliance
- [ ] Input validation ở tất cả endpoints
- [ ] Error message sanitization (không leak internal info)
- [ ] Rate limiting implementation
- [ ] HTTPS setup
- [ ] CORS configuration review

---

### Phase 5: Advanced Features (Optional, phụ thuộc tiến độ)

- [ ] **Music Taste Profile:** Analyze user preferences over time
- [ ] **Social Features:** Share recommendations with friends
- [ ] **Trending Recommendations:** Time-based trending analysis
- [ ] **Recommendation Explanation:** Why this song was recommended?
- [ ] **Cold Start Solution:** Initial recommendations cho new users
- [ ] **Real-time Updates:** WebSocket support cho live rating updates
- [ ] **Multi-language Support:** i18n implementation

---

## IV. TIMELINE & MILESTONES

| Phase | Task | Timeline | Priority |
|-------|------|----------|----------|
| 1 | Caching + Performance Testing | Tuần 1-3 | **HIGH** |
| 1 | Logging & Monitoring | Tuần 2-3 | **HIGH** |
| 2 | Evaluation Metrics | Tuần 4-5 | **HIGH** |
| 2 | Collaborative Filtering | Tuần 6-7 | **MEDIUM** |
| 2 | Hybrid Approach | Tuần 7-8 | **MEDIUM** |
| 3 | Frontend UI Enhancements | Tuần 9-10 | **MEDIUM** |
| 3 | Backend APIs Extension | Tuần 9-11 | **MEDIUM** |
| 4 | Testing | Tuần 12-13 | **HIGH** |
| 4 | Documentation | Tuần 13-14 | **HIGH** |
| 4 | Deployment | Tuần 14-15 | **HIGH** |

---

## V. KỲ VỌNG OUTPUT CUỐI CÙNG

### Product
- ✅ Fully functional music recommendation system
- ✅ Web UI cho user interactions
- ✅ REST API documentation
- ✅ Docker deployment package
- ✅ Evaluation report với metrics

### Documentation
- ✅ Architecture & design document
- ✅ API documentation (Swagger)
- ✅ Database schema & ERD
- ✅ Algorithm explanation & comparison
- ✅ Deployment & setup guide
- ✅ Performance benchmark report

### Testing & Evaluation
- ✅ Unit test coverage > 70%
- ✅ Performance metrics (latency, throughput)
- ✅ Recommendation quality metrics (Precision, Recall, NDCG)
- ✅ User acceptance testing results
- ✅ Security audit checklist

---

## VI. RỦI RO & MITIGATION STRATEGY

| Rủi ro | Mô tả | Giải pháp |
|--------|-------|----------|
| Dataset quá nhỏ | Chỉ ~1000 bài hát → khó demo | Mở rộng dataset, dùng sample Spotify API |
| Cold-start problem | New items/users không có recommendations | Implement content-based fallback, popular songs |
| Performance | Multiple service calls → slow | Implement caching, async processing |
| Model drift | Recommendations outdated theo thời gian | Regular retraining, user feedback loop |
| Integration issues | Python-Java communication | Proper error handling, circuit breaker |

---

## VII. KẾT LUẬN

**Tính năng cơ bản:** ✅ Hoàn thành 70%
- Frontend: Music search + display ✅
- Backend: REST API layer ✅
- AI: Content-based recommendation ✅
- Integration: Three-tier working ✅

**Cần hoàn thiện:** 30%
- Evaluation & benchmarking
- Caching & performance optimization
- Advanced algorithms (Collaborative Filtering)
- Production deployment
- Comprehensive testing

**Dự kiến hoàn tất:** Tháng 5/2026 (khoảng 6-8 tuần từ hiện tại)

---

**Ngày báo cáo:** Tháng 3, 2026  
**Trạng thái:** On track, ready for optimization phase
