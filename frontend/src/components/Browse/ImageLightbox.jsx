import React, { useEffect } from 'react'
import { X, ChevronLeft, ChevronRight, FileText, Eye, Wand2, Loader2 } from 'lucide-react'
import styles from './ImageLightbox.module.css'

/**
 * Image lightbox component for viewing full-size images with details.
 *
 * @param {boolean} isOpen - Whether the lightbox is open
 * @param {Object} image - The selected image object
 * @param {boolean} analyzing - Whether AI analysis is in progress
 * @param {string} selectedModel - Selected vision model for analysis
 * @param {function} onClose - Function to close the lightbox
 * @param {function} onNavigate - Function to navigate to next/previous image (-1 or 1)
 * @param {function} onAnalyze - Function to trigger AI analysis
 */
const ImageLightbox = ({
  isOpen,
  image,
  analyzing,
  selectedModel,
  onClose,
  onNavigate,
  onAnalyze
}) => {
  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') onNavigate(-1)
      if (e.key === 'ArrowRight') onNavigate(1)
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, onNavigate])

  if (!isOpen || !image) return null

  return (
    <div className={styles.lightbox} onClick={onClose}>
      <div className={styles.lightboxContent} onClick={(e) => e.stopPropagation()}>
        <button className={styles.closeBtn} onClick={onClose}>
          <X size={24} />
        </button>

        <button className={styles.navBtn} onClick={() => onNavigate(-1)}>
          <ChevronLeft size={32} />
        </button>

        <div className={styles.lightboxMain}>
          <div className={styles.lightboxImage}>
            <img
              src={`/api/images/${image.id}/full`}
              alt={image.filename}
            />
          </div>

          <div className={styles.lightboxSidebar}>
            <h3>{image.filename}</h3>

            <div className={styles.detailSection}>
              <h4>Details</h4>
              {image.width && image.height && (
                <p><strong>Size:</strong> {image.width}×{image.height}</p>
              )}
              {image.size_bytes && (
                <p><strong>File:</strong> {(image.size_bytes / 1024).toFixed(1)} KB</p>
              )}
            </div>

            {image.ocr_text && (
              <div className={styles.detailSection}>
                <h4><FileText size={14} /> OCR Text</h4>
                <p className={styles.ocrText}>{image.ocr_text}</p>
              </div>
            )}

            <div className={styles.detailSection}>
              <h4><Eye size={14} /> AI Description</h4>
              {image.vision_description ? (
                <p className={styles.description}>{image.vision_description}</p>
              ) : (
                <div className={styles.noDescription}>
                  <p>No AI description</p>
                  <button
                    onClick={() => onAnalyze(image.id)}
                    disabled={analyzing || !selectedModel}
                  >
                    {analyzing ? <Loader2 size={14} className={styles.spin} /> : <Wand2 size={14} />}
                    Generate
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <button className={styles.navBtn} onClick={() => onNavigate(1)}>
          <ChevronRight size={32} />
        </button>
      </div>
    </div>
  )
}

export default ImageLightbox
