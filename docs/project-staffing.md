# Tạo dự án mới và chọn nhân viên phù hợp

Ngày cập nhật: **18/09/2026**. Base commit đầu đợt: `0b6d44b`, có thay đổi
worktree chưa commit. Phạm vi: hoàn thiện luồng local BE/FE đã có; không tự
tạo dự án/nhân viên thật, không ghi lên graph đang dùng.

## 1. Trả lời câu hỏi nghiệp vụ

**Admin đã có thể tạo dự án và xem nhân viên nội bộ tiềm năng để lựa chọn.**
Thông tin đầu vào gồm hai phần khác nhau:

| Nhập ở đâu? | Thông tin | Dùng để làm gì? |
| --- | --- | --- |
| Dự án → Thêm dự án | Mã, tên, mô tả, trạng thái | Lưu và trình bày thông tin dự án |
| Chi tiết → Yêu cầu kỹ năng | Kỹ năng, cấp tối thiểu 1–5, ưu tiên MUST/SHOULD/NICE | Làm căn cứ đối chiếu nhân viên |
| Phân tích & gợi ý → Kế hoạch phân công | Từ ngày, đến ngày, tỷ lệ cần phân bổ | Kiểm tra dung lượng và lọc gợi ý trong kỳ |
| Hồ sơ nhân viên | Kỹ năng hiện có, cấp độ, kinh nghiệm, trạng thái | Dữ liệu nguồn để tìm người phù hợp |

**Tên/mô tả không tự được phân tích thành yêu cầu kỹ năng.** Ví dụ nhập “xây
website bán hàng bằng Python” chỉ tạo mô tả. Cần khai báo Python/FastAPI/Docker
trong tab Yêu cầu kỹ năng thì hệ thống mới đối chiếu được. Chưa dùng LLM,
AI suy luận mô tả, embedding hoặc tự đọc CV.

Không cần phân công một đội trước khi xem gợi ý: dự án chưa có thành viên
nhưng có yêu cầu sẽ có các kỹ năng MISSING, dùng được để tìm đội ban đầu.

## 2. Hướng dẫn sử dụng

1. Admin vào **Dự án → Thêm dự án**, nhập mã duy nhất như `PROJ950`, tên,
   mô tả và trạng thái. Nhấn Lưu thay đổi.
2. Sau khi tạo thành công, trang danh sách hiện thông báo có tên dự án và nút
   **Khai báo yêu cầu cho dự án vừa tạo**. Không tự gán người hoặc ghi thêm
   yêu cầu. Nếu tạo thất bại, giữ biểu mẫu và không thông báo thành công.
3. Khai báo từng yêu cầu, ví dụ Python cấp 3 MUST; Docker cấp 3 SHOULD.
   Nếu danh mục chưa có kỹ năng đó, Admin tạo trong trang Kỹ năng trước.
4. Bấm **Xem ứng viên theo yêu cầu đã khai báo**, hoặc tab Phân tích & gợi ý.
   Chọn kỳ và % cần phân bổ, rồi bấm Áp dụng kế hoạch. Mặc định là hôm nay–
   hôm nay và cần 20%; muốn công việc dài hơn cần chọn khoảng ngày thích hợp.
5. Xem từng ứng viên: mã/tên, chức danh/cấp bậc, địa điểm; kỹ năng khớp,
   cấp đang có so với cấp yêu cầu, số năm kinh nghiệm, ưu tiên yêu cầu;
   dung lượng tối thiểu còn lại trong kỳ và thông tin cộng tác.
6. Dùng **Xem hồ sơ nhân viên** để đọc hồ sơ đầy đủ. Liên kết điều hướng tới
   trang nhân viên; bộ lọc kế hoạch không được lưu lâu dài qua việc rời trang.
7. Bấm **Kiểm tra phân bổ** ở người muốn chọn. Ngày và % kế hoạch được truyền
   sang biểu mẫu. Xác nhận vai trò, thời gian và tỷ lệ; nhấn Lưu mới tạo/sửa
   `WORKS_ON`. BE kiểm tra quyền và tổng phân bổ không vượt 100% trong kỳ.
8. Xem tab **Đội ngũ** và phân tích được tải lại. Gợi ý là hỗ trợ quyết định,
   không tự động phân công hoặc bảo đảm rằng người đó phù hợp mọi mặt.

Trang chi tiết có hướng dẫn ba bước liên kết tới Yêu cầu → Gợi ý → Đội ngũ,
không phải wizard có transaction chung. Dự án đã lưu vẫn tồn tại nếu người
dùng dừng trước khi thêm yêu cầu; có thể mở lại để tiếp tục.

## 3. Cách gợi ý đang hoạt động

Giữ thuật toán của [phân bổ theo thời gian](allocation-planning.md):

- Đối chiếu kỹ năng dự án cần với người được phân công xuyên suốt kỳ lựa chọn.
- Tìm nhân viên trạng thái AVAILABLE, chưa có quan hệ với dự án và đáp ứng
  cấp độ của ít nhất một kỹ năng GAP/MISSING.
- Tính tải cao nhất trong kỳ và xem có đủ % được yêu cầu hay không.
- Có bộ lọc chỉ người đủ dung lượng; trong kết quả, ưu tiên đủ dung lượng,
  số kỹ năng khớp, cộng tác, tổng cấp độ khớp và ID ổn định.
- Đợt này **không đổi cách xếp hạng**, chỉ làm rõ đầu vào/trạng thái/thông tin
  quyết định. Số năm kinh nghiệm và ưu tiên được hiển thị, chưa thêm trọng số
  hoặc điều kiện loại ứng viên mới.

“Đáp ứng 2/3 kỹ năng còn thiếu” không phải 2/3 toàn bộ yêu cầu của dự án, cũng
không phải điểm nhân viên. Một người đáp ứng ít nhất một yêu cầu đã có thể được
gợi ý để bổ sung cho đội; không bảo đảm đáp ứng mọi kỹ năng MUST. Không dùng
allocation hoặc thứ hạng này để tự động đánh giá hiệu suất/thưởng/phạt.

## 4. Sửa lỗi trạng thái thiếu dữ liệu

Trước cập nhật, `uncovered_skill_count=0` xuất hiện ở cả dự án chưa có yêu cầu
lẫn dự án đã đủ kỹ năng, khiến FE có thể báo “Đội ngũ đã đáp ứng kỹ năng” sai.

API gợi ý bổ sung `summary.required_skill_count` là số kỹ năng yêu cầu đã khai
báo. FE phân biệt:

| Trạng thái | Hiển thị |
| --- | --- |
| `required_skill_count = 0` | Chưa đủ thông tin để gợi ý nhân viên; giải thích phải khai báo yêu cầu; người có quyền có link sang khai báo, ẩn form lọc chưa có căn cứ |
| Có yêu cầu, `uncovered_skill_count > 0`, không có ứng viên | Chưa có ứng viên phù hợp; hướng dẫn đổi kỳ/%/lọc và kiểm tra hồ sơ |
| Có yêu cầu, `uncovered_skill_count = 0` | Đội ngũ đã đáp ứng kỹ năng trong phạm vi phân tích |
| API lỗi | Hiển thị lỗi và thử lại; không suy ra chưa có yêu cầu hoặc đã đủ đội |

Không thêm truy vấn graph để lấy số lượng này: service dùng số dòng kỹ năng
của kết quả skill-gap vốn đã đọc. Dự án không có yêu cầu không truy vấn tìm
ứng viên hoặc tải ứng viên. Không tạo quan hệ khi GET recommendations.

## 5. API, file và quyền

Các API đã có được tiếp tục dùng:

- `POST /api/projects`: Admin tạo thông tin dự án.
- `PUT /api/projects/{id}/requirements/{skill_id}`: Admin/Manager được giao
  dự án khai báo yêu cầu.
- `GET /api/projects/{id}/skill-gap`: đối chiếu kỹ năng hôm nay.
- `GET /api/projects/{id}/recommendations?...`: gợi ý theo kế hoạch, trả thêm
  trường `summary.required_skill_count` (số nguyên không âm).
- `GET /api/employees/{id}` và `/skills`: dữ liệu hồ sơ nhân viên.
- `PUT /api/projects/{id}/assignments/{employee_id}`: xác nhận phân công.

Không thêm endpoint hoặc mở rộng quyền. Manager không tạo dự án mới, chỉ ghi
vào dự án được cấp; Viewer được xem hồ sơ/gợi ý nhưng không có nút ghi. Khi dự
án thiếu yêu cầu, Viewer được nhắc liên hệ Admin/Manager thay vì được mời thao
tác ghi. Link điều hướng trong hướng dẫn không phải quyền ghi; BE vẫn kiểm
tra mọi request theo phiên/CSRF và scope dự án.

File chính:

- `backend/app/services/candidate_recommendation_service.py`: count yêu cầu ở
  mọi nhánh (chưa cấu hình, đã đủ, có/không ứng viên).
- `backend/app/schemas/candidate_recommendation.py`: hợp đồng response.
- `frontend/src/pages/Directory.tsx`: nhắc trước tạo, chuyển tiếp sau thành công.
- `frontend/src/pages/Details.tsx`: hướng dẫn ba bước trong chi tiết.
- `frontend/src/components/Relations.tsx`: hướng dẫn yêu cầu và link xem ứng viên.
- `frontend/src/components/Analysis.tsx`: phân biệt trạng thái, thông tin kỹ
  năng/kinh nghiệm và link hồ sơ trên thẻ ứng viên.
- `frontend/src/types.ts`, `styles.css`: contract và bố cục desktop/mobile.
- `backend/tests/test_project_staffing.py`, `frontend/tests/project-staffing.spec.ts`:
  test mới; cập nhật fixture RBAC và expected summary trong graph E2E/diagnostic.

## 6. Cài đặt và tương thích

Không thêm dependency/env variable, không thay cấu trúc graph hoặc SQLite,
không migration/seed/backfill. Khởi động lại BE và FE cùng phiên bản để nhận
trường mới. Không sửa `.env`, tài khoản, graph thật hoặc export lại gói bàn giao.
Client cũ bỏ qua trường response bổ sung vẫn đọc được; client mới cần BE mới
để phân biệt trạng thái thiếu yêu cầu chính xác.

## 7. Kiểm chứng

Ngày chạy: 18/09/2026, Asia/Saigon; Windows, Python 3.12, Node 24, Edge headless.
API/service test dùng graph giả lập và SQLite tài khoản riêng; FE test dùng
HTTP mock. Không coi đây là nghiệm thu FE → BE → CognoDB thật.

```powershell
# backend
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q

# frontend, terminal tại thư mục frontend
npm run build
npm run format:check
npm test
npm run test:rbac
```

Test mới bao gồm:

- Tạo dự án có tên/mô tả nhắc công nghệ vẫn chưa có yêu cầu tự sinh.
- Sau PUT yêu cầu, dự án chưa có thành viên có thể trả ứng viên MISSING,
  đủ chi tiết cấp độ, kinh nghiệm và dung lượng; GET không tự phân công.
- Dự án không tồn tại vẫn 404, lỗi đọc graph vẫn 503; không trả trạng thái rỗng giả.
- FE đi từ tạo thành công → khai báo → xem ứng viên → xác nhận phân công;
  đối chiếu request ngày/% và chỉ một lần ghi khi bấm Lưu.
- Viewer thiếu yêu cầu chỉ nhận hướng dẫn liên hệ; no candidates khác covered.
- Tạo thất bại giữ dữ liệu, không hiện thông báo đã tạo; lỗi gợi ý không thành
  “đã đủ đội”. Layout 390px và kiểm tra accessibility tự động.

Kết quả thực chạy ngày 18/09/2026:

| Kiểm tra | Kết quả |
| --- | --- |
| Backend ngoại tuyến | **335 passed, 1 skipped, 9 deselected**, 150,08 giây; thêm 5 test mới. Skip bài symlink do quyền Windows; 9 integration không chạy |
| Frontend mặc định | **58 passed**, 2,4 phút; thêm 6 test mới, gồm luồng tạo → yêu cầu → gợi ý → xác nhận phân công |
| RBAC FE–FastAPI cô lập | **10 passed**, 36,5 giây; tài khoản/phiên/SQLite thật riêng, graph stub |
| TypeScript + build | PASS; JS 355,48 kB / gzip 109,41 kB; CSS 37,21 kB / gzip 8,17 kB |
| Ruff / Prettier / git diff whitespace | PASS ở kiểm tra cuối |
| Gói nguồn | `scripts.handoff check` PASS, 168 file; chưa xuất ZIP mới, chỉ kiểm tra allowlist/heuristic và đối chiếu secret local |
| QA giao diện | Đã xem ảnh luồng mới ở 390px; kiểm tra không tràn ngang và axe WCAG 2 A/AA, 2.1 AA đạt trong test |

Không dùng kết quả mock để tuyên bố dữ liệu đã lưu trên graph thật. Không chạy
nghiệm thu graph/race/backup-restore trong đợt này; không commit/push. File test
graph đã cập nhật hợp đồng summary nhưng vẫn chờ môi trường test riêng để chạy.

## 8. Giới hạn và phần chưa làm

- Không tự rút kỹ năng từ mô tả, không đề xuất số người/vai trò/ngân sách từ
  văn bản; chưa tối ưu tổ hợp toàn đội hoặc tính chi phí nhân sự.
- Không có yêu cầu tối thiểu riêng về số năm kinh nghiệm, bằng cấp hoặc kỹ
  năng được xác minh; các thông tin hiện có do người có quyền nhập.
- Coverage không trọng số; priority không đồng nghĩa hệ thống chỉ trả người
  đáp ứng toàn bộ MUST. Xem quy tắc thời gian cho giới hạn coverage cả kỳ.
- Không lưu shortlist, phê duyệt nhận việc hoặc gửi thông báo cho nhân viên.
- Đợt này không chạy graph thật, race, load test hay triển khai production.
  Tiếp tục nghiệm thu trên instance test riêng theo [quy trình graph E2E](graph-e2e-acceptance.md).
