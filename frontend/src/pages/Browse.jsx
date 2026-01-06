import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { 
  FileText, Image, X, ChevronLeft, ChevronRight, Eye, Wand2, 
  ZoomIn, Loader2, RefreshCw, FolderOpen, Grid, List, Filter
} from 'lucide-react'
import styles from './Browse.module.css'

// Tab types
const TABS = {
  FILES: 'files',
  IMAGES: 'images'
}

// Skeleton loader
const Skeleton = ({ width = '100%', height = '1rem' }) => (
  <div className={styles.skeleton} style={{ width, height }} />
)

function Browse() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') || TABS.FILES
  
  const [activeTab, setActiveTab] = useState(initialTab)
  const [viewMode, setViewMode] = useState('list') // 'list' or 'grid'
  const [sortBy, setSortBy] = useState('created_at-desc') // Sort option for files
  const [imageSortBy, setImageSortBy] = useState('created_at-desc') // Sort option for images
  
  // Files state
  const [files, setFiles] = useState([])
  const [filesTotal, setFilesTotal] = useState(0)
  const [filesPage, setFilesPage] = useState(1)
  const [filesLoading, setFilesLoading] = useState(true)
  
  // Images state
  const [images, setImages] = useState([])
  const [imagesTotal, setImagesTotal] = useState(0)
  const [imagesPage, setImagesPage] = useState(0)
  const [imagesLoading, setImagesLoading] = useState(true)
  const [imageFilter, setImageFilter] = useState('all')
  
  // Lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [selectedImage, setSelectedImage] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [visionModels, setVisionModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  
  // Counts for tabs
  const [counts, setCounts] = useState({ files: 0, images: 0 })
  
  const filesLimit = 50
  const imagesLimit = 24

  // Fetch counts for tab badges
  const fetchCounts = useCallback(async () => {
    try {
      const [filesRes, imagesRes] = await Promise.all([
        fetch('/api/files?skip=0&limit=1'),
        fetch('/api/images?skip=0&limit=1')
      ])
      const filesData = await filesRes.json()
      const imagesData = await imagesRes.json()
      setCounts({
        files: filesData.total || 0,
        images: imagesData.total || 0
      })
    } catch (err) {
      console.error('Failed to fetch counts:', err)
    }
  }, [])

  // Files fetching
  const fetchFiles = useCallback(async () => {
    setFilesLoading(true)
    try {
      const skip = (filesPage - 1) * filesLimit
      const [sortField, sortDir] = sortBy.split('-')
      const res = await fetch(`/api/files?skip=${skip}&limit=${filesLimit}&sort_by=${sortField}&sort_dir=${sortDir}`)
      const data = await res.json()
      setFiles(data.files || [])
      setFilesTotal(data.total || 0)
    } catch (err) {
      console.error('Failed to fetch files:', err)
    } finally {
      setFilesLoading(false)
    }
  }, [filesPage, sortBy])

  // Images fetching
  const fetchImages = useCallback(async () => {
    setImagesLoading(true)
    try {
      const [sortField, sortDir] = imageSortBy.split('-')
      let url = `/api/images?skip=${imagesPage * imagesLimit}&limit=${imagesLimit}&sort_by=${sortField}&sort_dir=${sortDir}`
      if (imageFilter === 'with-description') url += '&has_description=true'
      else if (imageFilter === 'without-description') url += '&has_description=false'

      const res = await fetch(url)
      const data = await res.json()
      setImages(data.items || [])
      setImagesTotal(data.total || 0)
    } catch (err) {
      console.error('Failed to fetch images:', err)
    } finally {
      setImagesLoading(false)
    }
  }, [imagesPage, imageFilter, imageSortBy])

  const fetchVisionModels = useCallback(async () => {
    try {
      const res = await fetch('/api/vision/models')
      const data = await res.json()
      setVisionModels(data.available || [])
      setSelectedModel(data.default || '')
    } catch (err) {
      console.error('Failed to fetch vision models:', err)
    }
  }, [])

  // Update URL when tab changes
  const changeTab = (tab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  // Initial load
  useEffect(() => {
    fetchCounts()
    fetchVisionModels()
  }, [fetchCounts, fetchVisionModels])

  // Load data when tab or page changes
  useEffect(() => {
    if (activeTab === TABS.FILES) {
      fetchFiles()
    }
  }, [activeTab, fetchFiles])

  useEffect(() => {
    if (activeTab === TABS.IMAGES) {
      fetchImages()
    }
  }, [activeTab, fetchImages])

  // Image analysis
  const analyzeImage = async (imageId) => {
    setAnalyzing(true)
    try {
      const res = await fetch(`/api/images/${imageId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel })
      })
      const data = await res.json()
      
      setImages(prev => prev.map(img => 
        img.id === imageId 
          ? { ...img, vision_description: data.vision_description, has_description: true }
          : img
      ))
      
      if (selectedImage?.id === imageId) {
        setSelectedImage(prev => ({ ...prev, vision_description: data.vision_description }))
      }
    } catch (err) {
      console.error('Failed to analyze image:', err)
    } finally {
      setAnalyzing(false)
    }
  }

  // Lightbox
  const openLightbox = async (image) => {
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

  const filesTotalPages = Math.ceil(filesTotal / filesLimit)
  const imagesTotalPages = Math.ceil(imagesTotal / imagesLimit)

  return (
    <div className={styles.page}>
      {/* Header with Tabs */}
      <div className={styles.header}>
        <div className={styles.tabs}>
          <button 
            className={`${styles.tab} ${activeTab === TABS.FILES ? styles.active : ''}`}
            onClick={() => changeTab(TABS.FILES)}
          >
            <FileText size={18} />
            Files
            <span className={styles.tabCount}>{counts.files.toLocaleString()}</span>
          </button>
          <button 
            className={`${styles.tab} ${activeTab === TABS.IMAGES ? styles.active : ''}`}
            onClick={() => changeTab(TABS.IMAGES)}
          >
            <Image size={18} />
            Images
            <span className={styles.tabCount}>{counts.images.toLocaleString()}</span>
          </button>
        </div>
        
        <div className={styles.headerActions}>
          {activeTab === TABS.IMAGES && (
            <>
              <select 
                value={imageFilter} 
                onChange={(e) => { setImageFilter(e.target.value); setImagesPage(0); }}
                className={styles.filterSelect}
              >
                <option value="all">All Images</option>
                <option value="with-description">With AI Description</option>
                <option value="without-description">Without Description</option>
              </select>
            </>
          )}

        </div>
      </div>

      {/* Files Tab Content */}
      {activeTab === TABS.FILES && (
        <div className={styles.content}>
          {/* Controls Bar */}
          <div className={styles.controls}>
            <div className={styles.controlsLeft}>
              <Filter size={16} />
              <select 
                value={sortBy} 
                onChange={(e) => setSortBy(e.target.value)}
                className={styles.sortSelect}
              >
                <option value="created_at-desc">Newest First (Added to DB)</option>
                <option value="created_at-asc">Oldest First (Added to DB)</option>
                <option value="modified_at-desc">Recently Modified</option>
                <option value="modified_at-asc">Least Recently Modified</option>
                <option value="filename-asc">Filename (A-Z)</option>
                <option value="filename-desc">Filename (Z-A)</option>
                <option value="size-desc">Largest First</option>
                <option value="size-asc">Smallest First</option>
              </select>
            </div>
            <div className={styles.controlsRight}>
              <button 
                onClick={() => setViewMode('list')}
                className={viewMode === 'list' ? styles.active : ''}
                title="List view"
              >
                <List size={18} />
              </button>
              <button 
                onClick={() => setViewMode('grid')}
                className={viewMode === 'grid' ? styles.active : ''}
                title="Grid view"
              >
                <Grid size={18} />
              </button>
            </div>
          </div>

          {filesLoading ? (
            <div className={styles.loadingList}>
              {[...Array(10)].map((_, i) => (
                <div key={i} className={styles.skeletonRow}>
                  <Skeleton width="20px" height="20px" />
                  <Skeleton width="60%" height="1rem" />
                  <Skeleton width="100px" height="0.8rem" />
                </div>
              ))}
            </div>
          ) : files.length === 0 ? (
            <div className={styles.empty}>
              <FolderOpen size={48} />
              <p>No files found</p>
            </div>
          ) : viewMode === 'list' ? (
            <div className={styles.fileList}>
              {files.map(file => (
                <Link to={`/document/${file.id}`} key={file.id} className={styles.fileRow}>
                  <FileText size={18} className={styles.fileIcon} />
                  <div className={styles.fileInfo}>
                    <span className={styles.fileName}>{file.filename}</span>
                    <span className={styles.filePath}>{file.path}</span>
                  </div>
                  <span className={styles.fileDate}>
                    {new Date(file.created_at).toLocaleDateString()}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <div className={styles.fileGrid}>
              {files.map(file => (
                <Link to={`/document/${file.id}`} key={file.id} className={styles.fileCard}>
                  <FileText size={32} />
                  <span className={styles.fileName}>{file.filename}</span>
                  <span className={styles.fileDate}>
                    {new Date(file.created_at).toLocaleDateString()}
                  </span>
                </Link>
              ))}
            </div>
          )}

          {filesTotalPages > 1 && (
            <div className={styles.pagination}>
              <button 
                onClick={() => setFilesPage(p => Math.max(1, p - 1))}
                disabled={filesPage === 1}
              >
                <ChevronLeft size={16} /> Prev
              </button>
              <span>Page {filesPage} of {filesTotalPages}</span>
              <button 
                onClick={() => setFilesPage(p => Math.min(filesTotalPages, p + 1))}
                disabled={filesPage === filesTotalPages}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Images Tab Content */}
      {activeTab === TABS.IMAGES && (
        <div className={styles.content}>
          {/* Controls Bar */}
          <div className={styles.controls}>
            <div className={styles.controlsLeft}>
              <Filter size={16} />
              <select
                value={imageSortBy}
                onChange={(e) => setImageSortBy(e.target.value)}
                className={styles.sortSelect}
              >
                <option value="created_at-desc">Newest First (Added to DB)</option>
                <option value="created_at-asc">Oldest First (Added to DB)</option>
                <option value="modified_at-desc">Recently Modified</option>
                <option value="modified_at-asc">Least Recently Modified</option>
                <option value="filename-asc">Filename (A-Z)</option>
                <option value="filename-desc">Filename (Z-A)</option>
                <option value="size-desc">Largest First</option>
                <option value="size-asc">Smallest First</option>
              </select>
            </div>
          </div>

          {imagesLoading ? (
            <div className={styles.imageGrid}>
              {[...Array(12)].map((_, i) => (
                <div key={i} className={styles.imageSkeleton}>
                  <Skeleton width="100%" height="150px" />
                  <Skeleton width="80%" height="0.8rem" />
                </div>
              ))}
            </div>
          ) : images.length === 0 ? (
            <div className={styles.empty}>
              <Image size={48} />
              <p>No images found</p>
            </div>
          ) : (
            <div className={styles.imageGrid}>
              {images.map(image => (
                <div 
                  key={image.id} 
                  className={styles.imageCard}
                  onClick={() => openLightbox(image)}
                >
                  <div className={styles.imageThumb}>
                    {image.thumbnail_path ? (
                      <img 
                        src={`/api/images/${image.id}/thumbnail`} 
                        alt={image.filename}
                        loading="lazy"
                      />
                    ) : (
                      <div className={styles.noThumb}><Image size={32} /></div>
                    )}
                    <div className={styles.imageOverlay}>
                      <ZoomIn size={24} />
                    </div>
                  </div>
                  <div className={styles.imageInfo}>
                    <span className={styles.imageName}>{image.filename}</span>
                    <div className={styles.imageBadges}>
                      {image.has_description && <Eye size={12} title="Has AI description" />}
                      {image.ocr_text && <FileText size={12} title="Has OCR text" />}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {imagesTotalPages > 1 && (
            <div className={styles.pagination}>
              <button 
                onClick={() => setImagesPage(p => Math.max(0, p - 1))}
                disabled={imagesPage === 0}
              >
                <ChevronLeft size={16} /> Prev
              </button>
              <span>Page {imagesPage + 1} of {imagesTotalPages}</span>
              <button 
                onClick={() => setImagesPage(p => Math.min(imagesTotalPages - 1, p + 1))}
                disabled={imagesPage >= imagesTotalPages - 1}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
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
                  {selectedImage.width && selectedImage.height && (
                    <p><strong>Size:</strong> {selectedImage.width}×{selectedImage.height}</p>
                  )}
                  {selectedImage.size_bytes && (
                    <p><strong>File:</strong> {(selectedImage.size_bytes / 1024).toFixed(1)} KB</p>
                  )}
                </div>

                {selectedImage.ocr_text && (
                  <div className={styles.detailSection}>
                    <h4><FileText size={14} /> OCR Text</h4>
                    <p className={styles.ocrText}>{selectedImage.ocr_text}</p>
                  </div>
                )}

                <div className={styles.detailSection}>
                  <h4><Eye size={14} /> AI Description</h4>
                  {selectedImage.vision_description ? (
                    <p className={styles.description}>{selectedImage.vision_description}</p>
                  ) : (
                    <div className={styles.noDescription}>
                      <p>No AI description</p>
                      <button 
                        onClick={() => analyzeImage(selectedImage.id)}
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
            
            <button className={styles.navBtn} onClick={() => navigateImage(1)}>
              <ChevronRight size={32} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Browse
