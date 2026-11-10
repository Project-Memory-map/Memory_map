-- Chỉ chạy một lần trên database đã được tạo trước khi có users.facebook_id.
-- Database mới đã có cột và chỉ mục này trong schema.sql.
USE ban_do_ky_uc;

ALTER TABLE users
  ADD COLUMN facebook_id VARCHAR(191) NULL AFTER email,
  ADD UNIQUE KEY uq_users_facebook_id (facebook_id);

-- Giữ lại các liên kết Facebook đã có trong bảng OAuth chuẩn.
UPDATE users AS u
JOIN oauth_accounts AS oa
  ON oa.user_id = u.id AND oa.provider = 'facebook'
SET u.facebook_id = oa.provider_user_id
WHERE u.facebook_id IS NULL;
