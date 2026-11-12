-- Bản đồ Ký ức – Lược đồ cơ sở dữ liệu MySQL 8.0
-- Hướng dẫn chạy và lưu ý: xem database/README.md

-- ---------------------------------------------------------------------
-- PHẦN 0. TẠO DATABASE

CREATE DATABASE IF NOT EXISTS ban_do_ky_uc
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;                             -- không phân biệt dấu, hoa thường

USE ban_do_ky_uc;
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- PHẦN 1. MODULE TÀI KHOẢN (accounts)

-- 1.1 users – Tài khoản + hồ sơ cá nhân
CREATE TABLE IF NOT EXISTS users (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email               VARCHAR(255)  NULL,                 -- BR-08: duy nhất, lưu chữ thường
  password_hash       VARCHAR(255)  NULL,                 -- BR-07: chỉ lưu bản băm
  display_name        VARCHAR(100)  NOT NULL,             -- BR-12: tên hiển thị công khai
  avatar_path         VARCHAR(500)  NULL,
  bio                 VARCHAR(500)  NULL,
  role                ENUM('user','admin')    NOT NULL DEFAULT 'user',
  status              ENUM('active','locked') NOT NULL DEFAULT 'active',
  email_verified_at   DATETIME      NULL,                 -- BR-18: NULL = chưa xác thực
  token_version       INT UNSIGNED  NOT NULL DEFAULT 0,   -- BR-20: thu hồi JWT cũ
  failed_login_count  TINYINT UNSIGNED NOT NULL DEFAULT 0,-- BR-15
  first_failed_at     DATETIME      NULL,                 -- BR-15
  login_locked_until  DATETIME      NULL,                 -- BR-15
  last_login_at       DATETIME      NULL,
  created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_users PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB COMMENT='Tài khoản và hồ sơ người dùng';

-- 1.2 oauth_accounts – Liên kết Google / Facebook
CREATE TABLE IF NOT EXISTS oauth_accounts (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id           BIGINT UNSIGNED NOT NULL,
  provider          ENUM('google','facebook') NOT NULL,
  provider_user_id  VARCHAR(191) NOT NULL,                -- id phía Google/Facebook
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_oauth_accounts PRIMARY KEY (id),
  UNIQUE KEY uq_oauth_provider_uid  (provider, provider_user_id),
  UNIQUE KEY uq_oauth_user_provider (user_id, provider),
  KEY idx_oauth_user (user_id),
  CONSTRAINT fk_oauth_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Liên kết OAuth Google/Facebook';

-- 1.3 password_reset_tokens – Quên mật khẩu (BR-14)
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  token_hash  CHAR(64) NOT NULL,                          -- SHA-256 của token
  expires_at  DATETIME NOT NULL,                          -- tạo + 30 phút
  used_at     DATETIME NULL,                              -- khác NULL = đã dùng
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id),
  UNIQUE KEY uq_reset_token (token_hash),
  KEY idx_reset_user (user_id),
  CONSTRAINT fk_reset_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Token đặt lại mật khẩu';

-- ---------------------------------------------------------------------
-- PHẦN 2. DANH MỤC KHU VỰC

-- 2.1 regions – Tỉnh / thành / khu vực
CREATE TABLE IF NOT EXISTS regions (
  id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name   VARCHAR(100) NOT NULL,                           -- "Đà Lạt"
  slug   VARCHAR(120) NOT NULL,                           -- "da-lat"
  level  ENUM('province','city','other') NOT NULL DEFAULT 'province',
  CONSTRAINT pk_regions PRIMARY KEY (id),
  UNIQUE KEY uq_regions_slug (slug)
) ENGINE=InnoDB COMMENT='Danh mục tỉnh/thành/khu vực';

-- ---------------------------------------------------------------------
-- PHẦN 3. MODULE KÝ ỨC (memories)

-- 3.1 memories – Ký ức ghim trên bản đồ
CREATE TABLE IF NOT EXISTS memories (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id      BIGINT UNSIGNED NOT NULL,                  -- chủ sở hữu (BR-02)
  region_id    BIGINT UNSIGNED NULL,
  title        VARCHAR(200)  NOT NULL,
  content      MEDIUMTEXT    NOT NULL,
  memory_date  DATE          NOT NULL,                    -- BR-05
  place_name   VARCHAR(255)  NOT NULL,
  latitude     DECIMAL(9,6)  NOT NULL,
  longitude    DECIMAL(9,6)  NOT NULL,
  visibility   ENUM('private','public') NOT NULL DEFAULT 'private', -- BR-01
  status       ENUM('active','hidden')  NOT NULL DEFAULT 'active',  -- hidden = admin ẩn
  deleted_at   DATETIME      NULL,                        -- BR-13: xóa mềm
  created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_memories PRIMARY KEY (id),
  KEY idx_mem_user_date  (user_id, memory_date),
  KEY idx_mem_public_geo (visibility, latitude, longitude),
  KEY idx_mem_region     (region_id, visibility),
  KEY idx_mem_pub        (visibility, status, deleted_at, latitude),
  FULLTEXT KEY ft_mem_search (title, place_name) WITH PARSER ngram,
  CONSTRAINT fk_mem_user   FOREIGN KEY (user_id)   REFERENCES users (id)   ON DELETE CASCADE,
  CONSTRAINT fk_mem_region FOREIGN KEY (region_id) REFERENCES regions (id) ON DELETE SET NULL,
  CONSTRAINT ck_mem_lat CHECK (latitude  BETWEEN -90  AND 90),
  CONSTRAINT ck_mem_lng CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB COMMENT='Ký ức ghim trên bản đồ';

-- 3.2 media – Ảnh / video của ký ức (BR-06, BR-17)
CREATE TABLE IF NOT EXISTS media (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  memory_id   BIGINT UNSIGNED NOT NULL,
  media_type  ENUM('image','video') NOT NULL,
  file_path   VARCHAR(500) NOT NULL,
  thumb_path  VARCHAR(500) NULL,
  mime_type   VARCHAR(100) NOT NULL,
  size_bytes  INT UNSIGNED NOT NULL,
  sort_order  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_media PRIMARY KEY (id),
  KEY idx_media_memory (memory_id, sort_order),
  CONSTRAINT fk_media_memory FOREIGN KEY (memory_id)
    REFERENCES memories (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Ảnh/video của ký ức';

-- 3.3 trips – Chuyến đi
CREATE TABLE IF NOT EXISTS trips (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id      BIGINT UNSIGNED NOT NULL,
  name         VARCHAR(150) NOT NULL,
  description  VARCHAR(500) NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT pk_trips PRIMARY KEY (id),
  KEY idx_trips_user (user_id),
  CONSTRAINT fk_trips_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Chuyến đi';

-- 3.4 trip_memories – Chuyến đi ↔ ký ức (BR-09)
CREATE TABLE IF NOT EXISTS trip_memories (
  trip_id    BIGINT UNSIGNED NOT NULL,
  memory_id  BIGINT UNSIGNED NOT NULL,
  added_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_trip_memories PRIMARY KEY (trip_id, memory_id),
  KEY idx_tm_memory (memory_id),
  CONSTRAINT fk_tm_trip   FOREIGN KEY (trip_id)   REFERENCES trips (id)    ON DELETE CASCADE,
  CONSTRAINT fk_tm_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Ký ức thuộc chuyến đi';

-- 3.5 hashtags – Danh mục hashtag (BR-06)
CREATE TABLE IF NOT EXISTS hashtags (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(30) COLLATE utf8mb4_0900_as_ci NOT NULL, -- phân biệt dấu, không có "#"
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_hashtags PRIMARY KEY (id),
  UNIQUE KEY uq_hashtags_name (name)
) ENGINE=InnoDB COMMENT='Danh mục hashtag';

-- 3.6 memory_hashtags – Ký ức ↔ hashtag
CREATE TABLE IF NOT EXISTS memory_hashtags (
  memory_id   BIGINT UNSIGNED NOT NULL,
  hashtag_id  BIGINT UNSIGNED NOT NULL,
  source      ENUM('manual','ai') NOT NULL DEFAULT 'manual', -- ai = Gemini gợi ý
  CONSTRAINT pk_memory_hashtags PRIMARY KEY (memory_id, hashtag_id),
  KEY idx_mh_hashtag (hashtag_id, memory_id),
  CONSTRAINT fk_mh_memory  FOREIGN KEY (memory_id)  REFERENCES memories (id) ON DELETE CASCADE,
  CONSTRAINT fk_mh_hashtag FOREIGN KEY (hashtag_id) REFERENCES hashtags (id) ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='Hashtag gắn với ký ức';

-- ---------------------------------------------------------------------
-- PHẦN 4. MODULE QUẢN TRỊ (admin)

-- 4.1 admin_actions – Nhật ký thao tác quản trị (BR-10)
CREATE TABLE IF NOT EXISTS admin_actions (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  admin_id     BIGINT UNSIGNED NOT NULL,
  action       ENUM('hide_memory','unhide_memory','delete_memory','lock_user','unlock_user') NOT NULL,
  target_type  ENUM('memory','user') NOT NULL,
  target_id    BIGINT UNSIGNED NOT NULL,                  -- id ký ức hoặc user
  reason       VARCHAR(500) NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_admin_actions PRIMARY KEY (id),
  KEY idx_aa_target (target_type, target_id),
  KEY idx_aa_admin  (admin_id, created_at),
  CONSTRAINT fk_aa_admin FOREIGN KEY (admin_id)
    REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Nhật ký thao tác quản trị';

-- ---------------------------------------------------------------------
-- PHẦN 5. TRIGGER

DELIMITER $$

-- 5.1 users – Chuẩn hóa email (BR-08)
DROP TRIGGER IF EXISTS trg_users_bi $$
CREATE TRIGGER trg_users_bi
BEFORE INSERT ON users
FOR EACH ROW
BEGIN
  IF NEW.email IS NOT NULL THEN
    SET NEW.email = LOWER(TRIM(NEW.email));
  END IF;
END $$

-- 5.2 users – Chuẩn hóa email + tăng token_version khi đổi mật khẩu / bị khóa (BR-20)
DROP TRIGGER IF EXISTS trg_users_bu $$
CREATE TRIGGER trg_users_bu
BEFORE UPDATE ON users
FOR EACH ROW
BEGIN
  IF NEW.email IS NOT NULL THEN
    SET NEW.email = LOWER(TRIM(NEW.email));
  END IF;

  IF NOT (NEW.password_hash <=> OLD.password_hash)
     OR (NEW.status = 'locked' AND OLD.status <> 'locked') THEN
    SET NEW.token_version = OLD.token_version + 1;
  END IF;
END $$

-- 5.3 memories – Ngày ký ức không ở tương lai (BR-05)
DROP TRIGGER IF EXISTS trg_memories_bi $$
CREATE TRIGGER trg_memories_bi
BEFORE INSERT ON memories
FOR EACH ROW
BEGIN
  IF NEW.memory_date > CURDATE() THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-05: Ngày ký ức không được ở tương lai';
  END IF;
END $$

-- 5.4 memories – Ngày hợp lệ + không đổi chủ sở hữu (BR-05, BR-02)
DROP TRIGGER IF EXISTS trg_memories_bu $$
CREATE TRIGGER trg_memories_bu
BEFORE UPDATE ON memories
FOR EACH ROW
BEGIN
  IF NEW.memory_date > CURDATE() THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-05: Ngày ký ức không được ở tương lai';
  END IF;

  IF NEW.user_id <> OLD.user_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-02: Không được đổi chủ sở hữu ký ức';
  END IF;
END $$

-- 5.5 media – Tối đa 10 ảnh ≤ 5 MB, 1 video ≤ 50 MB (BR-06)
DROP TRIGGER IF EXISTS trg_media_bi $$
CREATE TRIGGER trg_media_bi
BEFORE INSERT ON media
FOR EACH ROW
BEGIN
  DECLARE v_count INT;

  SELECT COUNT(*) INTO v_count
  FROM media
  WHERE memory_id = NEW.memory_id
    AND media_type = NEW.media_type;

  IF NEW.media_type = 'image' THEN
    IF v_count >= 10 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'BR-06: Mỗi ký ức tối đa 10 ảnh';
    END IF;
    IF NEW.size_bytes > 5 * 1024 * 1024 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'BR-06: Mỗi ảnh tối đa 5 MB';
    END IF;
  ELSE
    IF v_count >= 1 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'BR-06: Mỗi ký ức tối đa 1 video';
    END IF;
    IF NEW.size_bytes > 50 * 1024 * 1024 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'BR-06: Video tối đa 50 MB';
    END IF;
  END IF;
END $$

-- 5.6 hashtags – Bỏ "#", chữ thường, chỉ chữ/số/"_" (BR-06)
DROP TRIGGER IF EXISTS trg_hashtags_bi $$
CREATE TRIGGER trg_hashtags_bi
BEFORE INSERT ON hashtags
FOR EACH ROW
BEGIN
  SET NEW.name = LOWER(TRIM(LEADING '#' FROM TRIM(NEW.name)));

  IF NEW.name = '' OR NOT REGEXP_LIKE(NEW.name, '^[\\p{L}\\p{N}_]+$') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-06: Hashtag chỉ gồm chữ, số, dấu _ và không có khoảng trắng';
  END IF;
END $$

-- 5.7 memory_hashtags – Tối đa 10 hashtag / ký ức (BR-06)
DROP TRIGGER IF EXISTS trg_memory_hashtags_bi $$
CREATE TRIGGER trg_memory_hashtags_bi
BEFORE INSERT ON memory_hashtags
FOR EACH ROW
BEGIN
  IF (SELECT COUNT(*) FROM memory_hashtags WHERE memory_id = NEW.memory_id) >= 10 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-06: Mỗi ký ức tối đa 10 hashtag';
  END IF;
END $$

-- 5.8 trip_memories – Chỉ thêm ký ức của chính chủ chuyến đi (BR-09)
DROP TRIGGER IF EXISTS trg_trip_memories_bi $$
CREATE TRIGGER trg_trip_memories_bi
BEFORE INSERT ON trip_memories
FOR EACH ROW
BEGIN
  IF (SELECT user_id FROM trips    WHERE id = NEW.trip_id)
     <> (SELECT user_id FROM memories WHERE id = NEW.memory_id) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-09: Chuyến đi chỉ chứa ký ức của chính chủ chuyến đi';
  END IF;
END $$

-- 5.9 admin_actions – Phải là admin, có lý do, không tự khóa mình (BR-10, BR-11)
DROP TRIGGER IF EXISTS trg_admin_actions_bi $$
CREATE TRIGGER trg_admin_actions_bi
BEFORE INSERT ON admin_actions
FOR EACH ROW
BEGIN
  IF (SELECT role FROM users WHERE id = NEW.admin_id) <> 'admin' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Chỉ quản trị viên mới được thực hiện thao tác này';
  END IF;

  IF (NEW.action IN ('lock_user','unlock_user') AND NEW.target_type <> 'user')
     OR (NEW.action IN ('hide_memory','unhide_memory','delete_memory') AND NEW.target_type <> 'memory') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'action không khớp target_type';
  END IF;

  IF NEW.action IN ('hide_memory','delete_memory','lock_user')
     AND (NEW.reason IS NULL OR TRIM(NEW.reason) = '') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-10: Thao tác ẩn/xóa/khóa phải có lý do';
  END IF;

  IF NEW.action = 'lock_user' AND NEW.target_id = NEW.admin_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'BR-11: Quản trị viên không được khóa chính tài khoản của mình';
  END IF;
END $$

-- 5.10 admin_actions – Không cho sửa nhật ký
DROP TRIGGER IF EXISTS trg_admin_actions_bu $$
CREATE TRIGGER trg_admin_actions_bu
BEFORE UPDATE ON admin_actions
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Nhật ký quản trị không được sửa';
END $$

-- 5.11 admin_actions – Không cho xóa nhật ký
DROP TRIGGER IF EXISTS trg_admin_actions_bd $$
CREATE TRIGGER trg_admin_actions_bd
BEFORE DELETE ON admin_actions
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Nhật ký quản trị không được xóa';
END $$

DELIMITER ;

-- ---------------------------------------------------------------------
-- PHẦN 6. VIEW

-- 6.1 v_public_memories – Ký ức hiện trên bản đồ cộng đồng (BR-03, BR-12)
CREATE OR REPLACE VIEW v_public_memories AS
SELECT
  m.id,
  m.title,
  m.content,
  m.memory_date,
  m.place_name,
  m.latitude,
  m.longitude,
  m.region_id,
  m.created_at,
  u.id           AS author_id,
  u.display_name AS author_name,
  u.avatar_path  AS author_avatar
FROM memories m
JOIN users u ON u.id = m.user_id
WHERE m.visibility = 'public'
  AND m.status     = 'active'
  AND m.deleted_at IS NULL
  AND u.status     = 'active';
