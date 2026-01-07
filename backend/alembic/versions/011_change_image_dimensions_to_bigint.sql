-- Change image dimension columns from INTEGER to BIGINT to support larger values
-- Migration: 011
-- Description: Convert image_width and image_height from INTEGER to BIGINT to prevent overflow errors on images with very large dimension metadata

-- Convert image_width from INTEGER to BIGINT
ALTER TABLE raw_files ALTER COLUMN image_width TYPE BIGINT;

-- Convert image_height from INTEGER to BIGINT
ALTER TABLE raw_files ALTER COLUMN image_height TYPE BIGINT;

-- Add comments explaining the change
COMMENT ON COLUMN raw_files.image_width IS 'Image width in pixels (BIGINT to support corrupted metadata with extreme values)';
COMMENT ON COLUMN raw_files.image_height IS 'Image height in pixels (BIGINT to support corrupted metadata with extreme values)';
