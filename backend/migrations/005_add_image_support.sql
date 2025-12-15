-- Migration: Add image and PDF support fields
-- Run against archive_brain database

-- Add file type classification
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT 'text';

-- Add image/PDF specific fields
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS ocr_text TEXT;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS vision_description TEXT;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS vision_model TEXT;

-- Add image metadata
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS image_width INTEGER;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS image_height INTEGER;

-- Create index for file_type queries
CREATE INDEX IF NOT EXISTS raw_files_file_type_idx ON raw_files(file_type);

-- Update existing records to have file_type based on extension
UPDATE raw_files SET file_type = 'text' WHERE file_type IS NULL;
UPDATE raw_files SET file_type = 'image' WHERE extension IN ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif');
UPDATE raw_files SET file_type = 'pdf' WHERE extension = '.pdf';
