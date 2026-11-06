-- ============================================================
-- Bản đồ Ký ức – Lược đồ cơ sở dữ liệu MySQL 8.0 (phiên bản 0.3)
-- Engine InnoDB, bộ ký tự utf8mb4.
-- Phần 1: bảng thuộc phạm vi phiên bản này.
-- Phần 2 (cuối file, đang để dạng chú thích): bảng Giai đoạn 2.
-- v0.3: vá theo review kỹ thuật — users có email_verified_at/token_version/
--   failed_login_count/first_failed_at/login_locked_until (BR-15, BR-18, BR-20);
--   hashtags.name rút còn VARCHAR(30) khớp BR-06; oauth_accounts thêm UNIQUE
--   (user_id, provider); memories thêm index idx_mem_pub cho truy vấn công khai.
-- ============================================================
CREATE DATABASE IF NOT EXISTS ban_do_ky_uc
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ban_do_ky_uc;
SET NAMES utf8mb4;

-- ---------- Module 1: Tài khoản ----------
CREATE TABLE users (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email         VARCHAR(255)  NULL,
  password_hash VARCHAR(255)  NULL,
  display_name  VARCHAR(100)  NOT NULL,
  avatar_path   VARCHAR(500)  NULL,
  bio           VARCHAR(500)  NULL,
  role          ENUM('user','admin')    NOT NULL DEFAULT 'user',
  status        ENUM('active','locked') NOT NULL DEFAULT 'active',
  email_verified_at  DATETIME NULL,          -- BR-18: chỉ gộp OAuth theo email khi khác NULL
  token_version       INT UNSIGNED NOT NULL DEFAULT 0,  -- BR-20: thu hồi JWT cũ ngay khi đổi/đặt lại mật khẩu
  failed_login_count  TINYINT UNSIGNED NOT NULL DEFAULT 0,  -- BR-15
  first_failed_at     DATETIME NULL,         -- BR-15: mốc bắt đầu đếm 15 phút
  login_locked_until  DATETIME NULL,         -- BR-15: tạm khóa đăng nhập tới thời điểm này
  last_login_at DATETIME      NULL,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE oauth_accounts (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id          BIGINT UNSIGNED NOT NULL,
  provider         ENUM('google','facebook') NOT NULL,
  provider_user_id VARCHAR(191) NOT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_oauth_provider_uid (provider, provider_user_id),
  UNIQUE KEY uq_oauth_user_provider (user_id, provider),  -- 1 user chỉ liên kết 1 lần/provider
  KEY idx_oauth_user (user_id),
  CONSTRAINT fk_oauth_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE password_reset_tokens (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at    DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_reset_token (token_hash),
  KEY idx_reset_user (user_id),
  CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- Module 3: Danh mục khu vực ----------
CREATE TABLE regions (
  id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(100) NOT NULL,
  slug  VARCHAR(120) NOT NULL,
  level ENUM('province','city','other') NOT NULL DEFAULT 'province',
  PRIMARY KEY (id),
  UNIQUE KEY uq_regions_slug (slug)
) ENGINE=InnoDB;

-- ---------- Module 2: Ký ức, ảnh/video, chuyến đi, hashtag ----------
CREATE TABLE memories (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  region_id   BIGINT UNSIGNED NULL,
  title       VARCHAR(200)  NOT NULL,
  content     MEDIUMTEXT    NOT NULL,
  memory_date DATE          NOT NULL,
  place_name  VARCHAR(255)  NOT NULL,
  latitude    DECIMAL(9,6)  NOT NULL,
  longitude   DECIMAL(9,6)  NOT NULL,
  visibility  ENUM('private','public') NOT NULL DEFAULT 'private',
  status      ENUM('active','hidden')  NOT NULL DEFAULT 'active',
  deleted_at  DATETIME      NULL,
  created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_mem_user_date (user_id, memory_date),
  KEY idx_mem_public_geo (visibility, latitude, longitude),
  KEY idx_mem_region (region_id, visibility),
  KEY idx_mem_pub (visibility, status, deleted_at, latitude),  -- truy vấn khám phá công khai (BR-03)
  FULLTEXT KEY ft_mem_search (title, place_name) WITH PARSER ngram,
  CONSTRAINT fk_mem_user   FOREIGN KEY (user_id)   REFERENCES users (id)   ON DELETE CASCADE,
  CONSTRAINT fk_mem_region FOREIGN KEY (region_id) REFERENCES regions (id) ON DELETE SET NULL,
  CONSTRAINT ck_mem_lat CHECK (latitude  BETWEEN -90  AND 90),
  CONSTRAINT ck_mem_lng CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB;

CREATE TABLE media (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  memory_id  BIGINT UNSIGNED NOT NULL,
  media_type ENUM('image','video') NOT NULL,
  file_path  VARCHAR(500) NOT NULL,
  thumb_path VARCHAR(500) NULL,
  mime_type  VARCHAR(100) NOT NULL,
  size_bytes INT UNSIGNED NOT NULL,
  sort_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_media_memory (memory_id, sort_order),
  CONSTRAINT fk_media_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trips (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  name        VARCHAR(150) NOT NULL,
  description VARCHAR(500) NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trips_user (user_id),
  CONSTRAINT fk_trips_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trip_memories (
  trip_id   BIGINT UNSIGNED NOT NULL,
  memory_id BIGINT UNSIGNED NOT NULL,
  added_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (trip_id, memory_id),
  KEY idx_tm_memory (memory_id),
  CONSTRAINT fk_tm_trip   FOREIGN KEY (trip_id)   REFERENCES trips (id)    ON DELETE CASCADE,
  CONSTRAINT fk_tm_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE hashtags (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name       VARCHAR(30) COLLATE utf8mb4_0900_as_ci NOT NULL,  -- khớp BR-06 (tối đa 30 ký tự, có dấu, phân biệt dấu)
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_hashtags_name (name)
) ENGINE=InnoDB;

CREATE TABLE memory_hashtags (
  memory_id  BIGINT UNSIGNED NOT NULL,
  hashtag_id BIGINT UNSIGNED NOT NULL,
  source     ENUM('manual','ai') NOT NULL DEFAULT 'manual',
  PRIMARY KEY (memory_id, hashtag_id),
  KEY idx_mh_hashtag (hashtag_id, memory_id),
  CONSTRAINT fk_mh_memory  FOREIGN KEY (memory_id)  REFERENCES memories (id) ON DELETE CASCADE,
  CONSTRAINT fk_mh_hashtag FOREIGN KEY (hashtag_id) REFERENCES hashtags (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- Module 4: Quản trị ----------
CREATE TABLE admin_actions (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  admin_id    BIGINT UNSIGNED NOT NULL,
  action      ENUM('hide_memory','unhide_memory','delete_memory','lock_user','unlock_user') NOT NULL,
  target_type ENUM('memory','user') NOT NULL,
  target_id   BIGINT UNSIGNED NOT NULL,
  reason      VARCHAR(500) NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_aa_target (target_type, target_id),
  KEY idx_aa_admin (admin_id, created_at),
  CONSTRAINT fk_aa_admin FOREIGN KEY (admin_id) REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- PHẦN 2 – GIAI ĐOẠN 2 (ngoài phạm vi phiên bản này).
-- Bỏ dấu "-- " ở đầu mỗi dòng khi bắt đầu làm tương tác cộng đồng.
-- ============================================================
-- CREATE TABLE memory_likes (
--   user_id    BIGINT UNSIGNED NOT NULL,
--   memory_id  BIGINT UNSIGNED NOT NULL,
--   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (user_id, memory_id),
--   KEY idx_likes_memory (memory_id),
--   CONSTRAINT fk_likes_user   FOREIGN KEY (user_id)   REFERENCES users (id)    ON DELETE CASCADE,
--   CONSTRAINT fk_likes_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
-- ) ENGINE=InnoDB;
--
-- CREATE TABLE comments (
--   id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
--   memory_id  BIGINT UNSIGNED NOT NULL,
--   user_id    BIGINT UNSIGNED NOT NULL,
--   content    VARCHAR(1000) NOT NULL,
--   deleted_at DATETIME NULL,
--   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (id),
--   KEY idx_cmt_memory (memory_id, created_at),
--   KEY idx_cmt_user (user_id),
--   CONSTRAINT fk_cmt_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE,
--   CONSTRAINT fk_cmt_user   FOREIGN KEY (user_id)   REFERENCES users (id)    ON DELETE CASCADE
-- ) ENGINE=InnoDB;
--
-- CREATE TABLE wishlist_items (
--   user_id    BIGINT UNSIGNED NOT NULL,
--   memory_id  BIGINT UNSIGNED NOT NULL,
--   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (user_id, memory_id),
--   KEY idx_wish_memory (memory_id),
--   CONSTRAINT fk_wish_user   FOREIGN KEY (user_id)   REFERENCES users (id)    ON DELETE CASCADE,
--   CONSTRAINT fk_wish_memory FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
-- ) ENGINE=InnoDB;
--
-- CREATE TABLE follows (
--   follower_id BIGINT UNSIGNED NOT NULL,
--   followee_id BIGINT UNSIGNED NOT NULL,
--   created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (follower_id, followee_id),
--   KEY idx_follow_followee (followee_id),
--   CONSTRAINT fk_follow_follower FOREIGN KEY (follower_id) REFERENCES users (id) ON DELETE CASCADE,
--   CONSTRAINT fk_follow_followee FOREIGN KEY (followee_id) REFERENCES users (id) ON DELETE CASCADE,
--   CONSTRAINT ck_follow_self CHECK (follower_id <> followee_id)
-- ) ENGINE=InnoDB;
--
-- CREATE TABLE reports (
--   id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
--   reporter_id BIGINT UNSIGNED NOT NULL,
--   target_type ENUM('memory','comment') NOT NULL,
--   target_id   BIGINT UNSIGNED NOT NULL,
--   reason      VARCHAR(500) NOT NULL,
--   status      ENUM('pending','resolved','rejected') NOT NULL DEFAULT 'pending',
--   handled_by  BIGINT UNSIGNED NULL,
--   handled_at  DATETIME NULL,
--   created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (id),
--   KEY idx_rep_status (status, created_at),
--   KEY idx_rep_target (target_type, target_id),
--   CONSTRAINT fk_rep_reporter FOREIGN KEY (reporter_id) REFERENCES users (id) ON DELETE CASCADE,
--   CONSTRAINT fk_rep_handler  FOREIGN KEY (handled_by)  REFERENCES users (id) ON DELETE SET NULL
-- ) ENGINE=InnoDB;
