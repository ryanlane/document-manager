import { useState, useEffect, useCallback } from 'react'
import { Image, X, ChevronLeft, ChevronRight, Eye, Wand2, FileText, ZoomIn, Loader2, RefreshCw } from 'lucide-react'
import styles from './Gallery.module.css'

function Gallery() {
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [filter, setFilter] = useState('all') // 'all', 'with-description', 'without-description'
  const [visionModels, setVisionModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 24

  useEffect(() => {
    fetchImages()
    fetchStats()
    fetchVisionModels()
  }, [page, filter])

  const fetchImages = async () => {
    setLoading(true)
    try {
      let url = `/api/images?skip=${page * limit}&limit=${limit}`
      if (filter === 'with-description') {
        url += '&has_description=true'
      } else if (filter === 'without-description') {
        url += '&has_description=false'
      }
      
      const res = await fetch(url)
      const data = await res.json()
      setImages(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      console.error('Failed to fetch images:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/images/stats')
      const data = await res.json()
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  const fetchVisionModels = async () => {
    try {
      const res = await fetch('/api/vision/models')
      const data = await res.json()
      setVisionModels(data.available || [])
      setSelectedModel(data.default || '')
    } catch (err) {
      console.error('Failed to fetch vision models:', err)
    }
  }

  const analyzeImage = async (imageId) => {
    setAnalyzing(true)
    try {
      const res = await fetch(`/api/images/${imageId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel })
      })
      const data = await res.json()
      
      // Update the image in the list
      setImages(prev => prev.map(img => 
        img.id === imageId 
          ? { ...img, vision_description: data.vision_description, vision_model: data.vision_model, has_description: true }
          : img
      ))
      
      // Update selected image if it's the one being analyzed
      if (selectedImage?.id === imageId) {
        setSelectedImage(prev => ({
          ...prev,
          vision_description: data.vision_description,
          vision_model: data.vision_model
        }))
      }
      
      fetchStats()
    } catch (err) {
      console.error('Failed to analyze image:', err)
      alert('Failed to analyze image. Make sure you have a vision model like llava installed.')
    } finally {
      setAnalyzing(false)
    }
  }

  const analyzeBatch = async () => {
    setAnalyzing(true)
    try {
      const res = await fetch(`/api/images/analyze-batch?limit=5&model=${selectedModel}`, {
        method: 'POST'
      })
      const data = await res.json()
      alert(`Analyzed ${data.processed} images. ${data.remaining} remaining.`)
      fetchImages()
      fetchStats()
    } catch (err) {
      console.error('Failed to batch analyze:', err)
      alert('Failed to analyze images.')
    } finally {
      setAnalyzing(false)
    }
  }

  const openLightbox = async (image) => {
    // Fetch full image details
    try {
      const res = await fetch(`/api/images/${image.id}`)
      const fullImage = await res.json()
      setSelectedImage(fullImage)
      setLightboxOpen(true)
    } catch (err) {
      console.error('Failed to fetch image details:', err)
    }
  }

  const closeLightbox = () => {
    setLightboxOpen(false)
    setSelectedImage(null)
  }

  const navigateImage = (direction) => {
    const currentIndex = images.findIndex(img => img.id === selectedImage?.id)
    if (currentIndex === -1) return
    
    let newIndex = currentIndex + direction
    if (newIndex < 0) newIndex = images.length - 1
    if (newIndex >= images.length) newIndex = 0
    
    openLightbox(images[newIndex])
  }

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!lightboxOpen) return
      
      if (e.key === 'Escape') closeLightbox()
      if (e.key === 'ArrowLeft') navigateImage(-1)
      if (e.key === 'ArrowRight') navigateImage(1)
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [lightboxOpen, selectedImage, images])

  const totalPages = Math.ceil(total / limit)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1><Image size={28} /> Image Gallery</h1>
        <p className={styles.subtitle}>Browse and analyze images from your archive</p>
      </header>

      {/* Stats Bar */}
      {stats && (
        <div className={styles.statsBar}>
          <div className={styles.stat}>
            <span className={styles.statValue}>{stats.total_images}</span>
            <span className={styles.statLabel}>Total Images</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{stats.with_vision_description}</span>
            <span className={styles.statLabel}>With AI Description</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{stats.with_ocr_text}</span>
            <span className={styles.statLabel}>With OCR Text</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{stats.without_description}</span>
            <span className={styles.statLabel}>Need Analysis</span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className={styles.controls}>
        <div className={styles.filterGroup}>
          <label>Filter:</label>
          <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(0); }}>
            <option value="all">All Images</option>
            <option value="with-description">With AI Description</option>
            <option value="without-description">Without AI Description</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label>Vision Model:</label>
          <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
            {visionModels.length === 0 && <option value="">No vision models found</option>}
            {visionModels.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </div>

        <button 
          className={styles.analyzeBtn}
          onClick={analyzeBatch}
          disabled={analyzing || !selectedModel || (stats?.without_description === 0)}
        >
          {analyzing ? <Loader2 size={16} className={styles.spin} /> : <Wand2 size={16} />}
          Analyze Batch (5)
        </button>

        <button className={styles.refreshBtn} onClick={() => { fetchImages(); fetchStats(); }}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Image Grid */}
      {loading ? (
        <div className={styles.loading}>
          <Loader2 size={32} className={styles.spin} />
          <p>Loading images...</p>
        </div>
      ) : images.length === 0 ? (
        <div className={styles.empty}>
          <Image size={48} />
          <p>No images found</p>
          <small>Add image files to your archive folders to see them here</small>
        </div>
      ) : (
        <>
          <div className={styles.grid}>
            {images.map(image => (
              <div 
                key={image.id} 
                className={styles.imageCard}
                onClick={() => openLightbox(image)}
              >
                <div className={styles.imageWrapper}>
                  {image.thumbnail_path ? (
                    <img 
                      src={`/api/images/${image.id}/thumbnail`} 
                      alt={image.filename}
                      loading="lazy"
                    />
                  ) : (
                    <div className={styles.noThumb}>
                      <Image size={32} />
                    </div>
                  )}
                  <div className={styles.imageOverlay}>
                    <ZoomIn size={24} />
                  </div>
                </div>
                <div className={styles.imageInfo}>
                  <span className={styles.imageName} title={image.filename}>
                    {image.filename}
                  </span>
                  <div className={styles.imageMeta}>
                    {image.width && image.height && (
                      <span>{image.width}×{image.height}</span>
                    )}
                    {image.has_description && (
                      <span className={styles.badge} title="Has AI description">
                        <Eye size={12} />
                      </span>
                    )}
                    {image.ocr_text && (
                      <span className={styles.badge} title="Has OCR text">
                        <FileText size={12} />
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button 
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span>Page {page + 1} of {totalPages}</span>
              <button 
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </>
      )}

      {/* Lightbox */}
      {lightboxOpen && selectedImage && (
        <div className={styles.lightbox} onClick={closeLightbox}>
          <div className={styles.lightboxContent} onClick={(e) => e.stopPropagation()}>
            <button className={styles.closeBtn} onClick={closeLightbox}>
              <X size={24} />
            </button>
            
            <button className={styles.navBtn} onClick={() => navigateImage(-1)}>
              <ChevronLeft size={32} />
            </button>
            
            <div className={styles.lightboxMain}>
              <div className={styles.lightboxImage}>
                <img 
                  src={`/api/images/${selectedImage.id}/full`} 
                  alt={selectedImage.filename}
                />
              </div>
              
              <div className={styles.lightboxSidebar}>
                <h3>{selectedImage.filename}</h3>
                
                <div className={styles.detailSection}>
                  <h4>Details</h4>
                  <p><strong>Size:</strong> {selectedImage.width}×{selectedImage.height}</p>
                  <p><strong>File size:</strong> {(selectedImage.size_bytes / 1024).toFixed(1)} KB</p>
                  <p><strong>Type:</strong> {selectedImage.extension}</p>
                </div>

                {selectedImage.ocr_text && (
                  <div className={styles.detailSection}>
                    <h4><FileText size={16} /> OCR Text</h4>
                    <p className={styles.ocrText}>{selectedImage.ocr_text}</p>
                  </div>
                )}

                <div className={styles.detailSection}>
                  <h4><Eye size={16} /> AI Description</h4>
                  {selectedImage.vision_description ? (
                    <>
                      <p className={styles.description}>{selectedImage.vision_description}</p>
                      <small className={styles.modelUsed}>Model: {selectedImage.vision_model}</small>
                    </>
                  ) : (
                    <div className={styles.noDescription}>
                      <p>No AI description yet</p>
                      <button 
                        onClick={() => analyzeImage(selectedImage.id)}
                        disabled={analyzing || !selectedModel}
                      >
                        {analyzing ? <Loader2 size={14} className={styles.spin} /> : <Wand2 size={14} />}
                        Generate Description
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <button className={styles.navBtn} onClick={() => navigateImage(1)}>
              <ChevronRight size={32} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Gallery
