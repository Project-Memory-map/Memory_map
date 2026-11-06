# Quy ước làm việc nhóm

## 1. Phân công theo module

| Module | Thư mục | Story | Người phụ trách |
|---|---|---|---|
| Core | `app/core/`, `app/shared/`, `app/main.py`, `app/models.py`, `database/`, `scripts/` | — | Cả nhóm (cần 2 người duyệt) |
| M1 — Tài khoản và người dùng | `app/modules/accounts/` (API + `ui/`) | US-ACC-001 → 008 | Thành viên 1 |
| M2 — Ký ức, chuyến đi, bản đồ | `app/modules/memories/` (API + `ui/`) | US-MEM-001 → 010 | Thành viên 2 |
| M3 — Khám phá, tìm kiếm | `app/modules/explore/` (API + `ui/`) | US-EXP-001 → 005 | Thành viên 3 |
| M4 — Quản trị | `app/modules/admin/` (API + `ui/`) | US-ADM-001 → 003 | Thành viên 4 |

Mỗi module chứa cả backend lẫn giao diện của chức năng đó, nên một story thường chỉ chạm vào đúng một thư mục module.

Điền tên thật vào cột cuối. Mỗi người chỉ sửa thư mục của module mình. Cần sửa module khác thì nhờ người phụ trách module đó duyệt PR.

## 2. Các nhánh

```
main ──────────●────────────────●──────────   bản ổn định, dùng để demo và nộp
                \              /
develop ──●──●──●──●──●──●──●──●──────────   nhánh tích hợp, mọi PR nhắm vào đây
           \    /  \     /
            feature/m1-acc-002-dang-nhap-email
                    feature/m3-exp-002-loc-hashtag
```

| Nhánh | Tạo từ | Merge vào | Dùng khi |
|---|---|---|---|
| `main` | — | — | Bản ổn định. Không commit trực tiếp. |
| `develop` | `main` | `main` (cuối sprint) | Tích hợp. Không commit trực tiếp. |
| `feature/<module>-<mã-story>-<mô-tả>` | `develop` | `develop` | Làm một user story |
| `feature/core-<mô-tả>` | `develop` | `develop` | Sửa phần dùng chung |
| `fix/<module>-<mô-tả>` | `develop` | `develop` | Sửa lỗi trong lúc phát triển |
| `hotfix/<mô-tả>` | `main` | `main` và `develop` | Sửa gấp bản đang demo |
| `docs/<mô-tả>` | `develop` | `develop` | Chỉ sửa tài liệu |

**Mã module:** `core`, `m1`, `m2`, `m3`, `m4`.

**Cách đặt tên:** chữ thường, không dấu, nối bằng gạch ngang, mã story bỏ tiền tố `US-`.

```
feature/m1-acc-001-dang-ky-email
feature/m1-acc-003-dang-nhap-google
feature/m2-mem-003-dinh-kem-anh
feature/m2-mem-009-chuyen-di
feature/m3-exp-003-loc-khu-vuc
feature/m4-adm-001-an-ky-uc
feature/core-geocode-cache
fix/m2-sai-thu-tu-anh
hotfix/loi-ket-noi-mysql
```

Một nhánh feature chỉ làm một story. Story lớn thì tách nhỏ (ví dụ `feature/m2-mem-003-dinh-kem-anh-backend` và `feature/m2-mem-003-dinh-kem-anh-frontend`).

## 3. Quy trình cho một story

```bash
git switch develop
git pull
git switch -c feature/m1-acc-002-dang-nhap-email

git add .
git commit -m "feat(m1): đăng nhập bằng email và mật khẩu"

git fetch origin
git rebase origin/develop
git push -u origin feature/m1-acc-002-dang-nhap-email
```

Sau đó mở Pull Request vào `develop`. Khi PR đã merge, xóa nhánh feature và chuyển thẻ Trello sang **Done**.

## 4. Commit

Dạng: `<loại>(<module>): <mô tả ngắn bằng tiếng Việt>`

| Loại | Dùng khi |
|---|---|
| `feat` | Thêm chức năng |
| `fix` | Sửa lỗi |
| `refactor` | Sửa code, không đổi hành vi |
| `test` | Thêm hoặc sửa kiểm thử |
| `docs` | Tài liệu |
| `chore` | Cấu hình, thư viện, script |
| `db` | Đổi `schema.sql` |

```
feat(m2): tạo ký ức bằng cách chọn vị trí trên bản đồ
fix(m3): bộ lọc hashtag bỏ sót ký ức có chữ hoa
db(core): thêm cột thumb_path cho media
docs: cập nhật BR-19 trong SRS
```

Dòng cuối thân commit ghi mã story liên quan: `Refs: US-MEM-002`.

## 5. Pull Request

- Mở vào `develop`, tiêu đề giống commit chính, điền đủ mẫu PR.
- Cần ít nhất 1 người duyệt. PR sửa `app/core/`, `app/shared/` hoặc `database/schema.sql` cần 2 người duyệt.
- Trước khi xin duyệt: chạy được `uvicorn`, `/api/health` trả 200, đã tự kiểm thử theo các AC của story.
- Dùng **Squash and merge** để lịch sử `develop` mỗi story một commit.

## 6. Cuối sprint

Một người tạo PR `develop → main` có tiêu đề `release: sprint N`. Cả nhóm chạy thử bản demo trên `develop` trước khi merge, sau đó gắn tag:

```bash
git switch main
git pull
git tag -a v0.N -m "Sprint N"
git push origin v0.N
```

## 7. Bảo vệ nhánh trên GitHub

Vào **Settings → Branches → Add branch ruleset**, áp dụng cho `main` và `develop`:

- Require a pull request before merging (1 approval)
- Block force pushes
- Restrict deletions
