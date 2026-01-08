// Modal utility functions
// Pure JavaScript - no external dependencies

/**
 * Open a modal by ID
 * @param {string} modalId - The ID of the modal element
 */
export function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(`Modal with ID "${modalId}" not found`);
        return;
    }
    
    modal.style.display = 'flex';
    
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
    
    // Set up event listeners for closing
    setupModalCloseHandlers(modal);
    
    // Focus the modal for accessibility
    modal.focus();
}

/**
 * Close a modal by ID
 * @param {string} modalId - The ID of the modal element
 */
export function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(`Modal with ID "${modalId}" not found`);
        return;
    }
    
    modal.style.display = 'none';
    
    // Restore body scroll
    document.body.style.overflow = '';
    
    // Clean up event listeners
    cleanupModalCloseHandlers(modal);
}

/**
 * Set up event listeners for closing the modal
 * - Click on overlay to close
 * - Click on close button to close
 * - Press Escape key to close
 * @param {HTMLElement} modal - The modal element
 */
function setupModalCloseHandlers(modal) {
    const modalId = modal.id;
    
    // Close on overlay click
    const overlay = modal.querySelector('.modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', () => closeModal(modalId));
    }
    
    // Close on close button click
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => closeModal(modalId));
    }
    
    // Close on Escape key
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            closeModal(modalId);
        }
    };
    document.addEventListener('keydown', escapeHandler);
    
    // Store handler for cleanup
    modal._escapeHandler = escapeHandler;
}

/**
 * Clean up event listeners for the modal
 * @param {HTMLElement} modal - The modal element
 */
function cleanupModalCloseHandlers(modal) {
    // Remove escape key handler
    if (modal._escapeHandler) {
        document.removeEventListener('keydown', modal._escapeHandler);
        delete modal._escapeHandler;
    }
}

/**
 * Set modal body content
 * @param {string} modalId - The ID of the modal element
 * @param {string} content - HTML content to set
 */
export function setModalContent(modalId, content) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(`Modal with ID "${modalId}" not found`);
        return;
    }
    
    const modalBody = modal.querySelector('.modal-body');
    if (modalBody) {
        modalBody.innerHTML = content;
    }
}

/**
 * Set modal loading state
 * @param {string} modalId - The ID of the modal element
 * @param {string} [message='Loading...'] - Loading message
 */
export function setModalLoading(modalId, message = 'Loading...') {
    setModalContent(modalId, `<div class="modal-loading">${message}</div>`);
}

/**
 * Set modal error state
 * @param {string} modalId - The ID of the modal element
 * @param {string} title - Error title
 * @param {string} message - Error message
 */
export function setModalError(modalId, title, message) {
    setModalContent(modalId, `
        <div class="modal-error">
            <div class="modal-error-title">${title}</div>
            <div class="modal-error-message">${message}</div>
        </div>
    `);
}
