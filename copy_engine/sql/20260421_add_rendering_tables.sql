-- Rendering integration tables for content_hub <-> video_engine
-- Compatible with MySQL 8+

START TRANSACTION;

CREATE TABLE IF NOT EXISTS render_jobs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  content_id BIGINT NOT NULL,
  provider VARCHAR(32) NOT NULL DEFAULT 'dsp',
  job_type VARCHAR(32) NOT NULL DEFAULT 'single_video',
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  priority INT NOT NULL DEFAULT 5,

  request_payload_json JSON NULL,
  latest_response_json JSON NULL,

  external_job_id VARCHAR(128) NULL,
  external_trace_id VARCHAR(128) NULL,

  retry_count INT NOT NULL DEFAULT 0,
  error_code VARCHAR(64) NULL,
  error_message TEXT NULL,

  submitted_by BIGINT NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,

  CONSTRAINT fk_render_jobs_content
    FOREIGN KEY (content_id) REFERENCES contents(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_render_jobs_user
    FOREIGN KEY (submitted_by) REFERENCES users(id)
    ON DELETE SET NULL,

  INDEX idx_render_jobs_content_id (content_id),
  INDEX idx_render_jobs_status (status),
  INDEX idx_render_jobs_provider (provider),
  INDEX idx_render_jobs_external_job_id (external_job_id)
);

CREATE TABLE IF NOT EXISTS media_assets (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  render_job_id BIGINT NOT NULL,
  content_id BIGINT NOT NULL,

  asset_type VARCHAR(32) NOT NULL,
  source_type VARCHAR(32) NOT NULL DEFAULT 'generated',
  provider VARCHAR(32) NOT NULL DEFAULT 'dsp',

  label VARCHAR(128) NULL,
  file_url TEXT NULL,
  local_path TEXT NULL,
  storage_key VARCHAR(255) NULL,
  mime_type VARCHAR(64) NULL,

  duration_seconds DECIMAL(10,2) NULL,
  file_size_bytes BIGINT NULL,
  checksum VARCHAR(128) NULL,

  metadata_json JSON NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,

  CONSTRAINT fk_media_assets_render_job
    FOREIGN KEY (render_job_id) REFERENCES render_jobs(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_media_assets_content
    FOREIGN KEY (content_id) REFERENCES contents(id)
    ON DELETE CASCADE,

  INDEX idx_media_assets_render_job_id (render_job_id),
  INDEX idx_media_assets_content_id (content_id),
  INDEX idx_media_assets_asset_type (asset_type)
);

CREATE TABLE IF NOT EXISTS storyboard_scenes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  render_job_id BIGINT NOT NULL,
  content_id BIGINT NOT NULL,

  seq_no INT NOT NULL,
  scene_id VARCHAR(64) NOT NULL,
  duration_seconds INT NOT NULL DEFAULT 3,

  narration TEXT NULL,
  onscreen_text TEXT NULL,
  shot_type VARCHAR(64) NULL,
  transition_name VARCHAR(64) NULL,
  objective TEXT NULL,

  visual_prompt TEXT NULL,
  negative_prompt TEXT NULL,
  camera_motion TEXT NULL,

  metadata_json JSON NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,

  CONSTRAINT fk_storyboard_scenes_render_job
    FOREIGN KEY (render_job_id) REFERENCES render_jobs(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_storyboard_scenes_content
    FOREIGN KEY (content_id) REFERENCES contents(id)
    ON DELETE CASCADE,

  UNIQUE KEY uk_storyboard_scene (render_job_id, scene_id),
  INDEX idx_storyboard_scenes_render_job_id (render_job_id),
  INDEX idx_storyboard_scenes_content_id (content_id),
  INDEX idx_storyboard_scenes_seq_no (seq_no)
);

CREATE TABLE IF NOT EXISTS audio_tracks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  title VARCHAR(255) NOT NULL,
  artist VARCHAR(255) NULL,
  platform VARCHAR(32) NOT NULL DEFAULT 'douyin',
  source_type VARCHAR(32) NOT NULL DEFAULT 'hot_music',

  mood_tag VARCHAR(64) NULL,
  bpm INT NULL,
  use_count BIGINT NULL,
  rank_no INT NULL,

  share_url TEXT NULL,
  cover_url TEXT NULL,
  external_ref VARCHAR(128) NULL,

  metadata_json JSON NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,

  INDEX idx_audio_tracks_platform (platform),
  INDEX idx_audio_tracks_source_type (source_type),
  INDEX idx_audio_tracks_rank_no (rank_no),
  INDEX idx_audio_tracks_external_ref (external_ref)
);

COMMIT;
