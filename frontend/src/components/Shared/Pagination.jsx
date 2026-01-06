import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import styles from './Pagination.module.css'

/**
 * Pagination component for navigating through pages of content.
 *
 * @param {number} currentPage - Current page number (1-indexed or 0-indexed depending on zeroIndexed)
 * @param {number} totalPages - Total number of pages
 * @param {function} onPageChange - Callback when page changes, receives new page number
 * @param {boolean} zeroIndexed - Whether pages are 0-indexed (default: false for 1-indexed)
 */
const Pagination = ({ currentPage, totalPages, onPageChange, zeroIndexed = false }) => {
  const minPage = zeroIndexed ? 0 : 1
  const maxPage = zeroIndexed ? totalPages - 1 : totalPages

  const handlePrevious = () => {
    onPageChange(Math.max(minPage, currentPage - 1))
  }

  const handleNext = () => {
    onPageChange(Math.min(maxPage, currentPage + 1))
  }

  const displayPage = zeroIndexed ? currentPage + 1 : currentPage

  return (
    <div className={styles.pagination}>
      <button
        onClick={handlePrevious}
        disabled={currentPage === minPage}
      >
        <ChevronLeft size={16} /> Prev
      </button>
      <span>Page {displayPage} of {totalPages}</span>
      <button
        onClick={handleNext}
        disabled={currentPage === maxPage}
      >
        Next <ChevronRight size={16} />
      </button>
    </div>
  )
}

export default Pagination
