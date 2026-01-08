// Modal utility functions
// Pure JavaScript - no external dependencies

// WeakMap to store event handlers for cleanup without memory leaks
const modalHandlers = new WeakMap();

// Store original body overflow value
let originalBodyOverflow = '';

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
    
    // Store original overflow value before modifying
    if (!originalBodyOverflow) {
        originalBodyOverflow = document.body.style.overflow || '';
    }
    
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
    
    // Set up event listeners for closing
    setupModalCloseHandlers(modal);
    
    // Focus the close button for accessibility (modal itself may not be focusable)
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.focus();
    } else {
        // Fallback: add tabindex to modal if no close button
        modal.setAttribute('tabindex', '-1');
        modal.focus();
    }
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
    
    // Restore original body scroll value
    document.body.style.overflow = originalBodyOverflow;
    originalBodyOverflow = '';
    
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
    const overlayHandler = () => closeModal(modalId);
    if (overlay) {
        overlay.addEventListener('click', overlayHandler);
    }
    
    // Close on close button click
    const closeBtn = modal.querySelector('.modal-close');
    const closeBtnHandler = () => closeModal(modalId);
    if (closeBtn) {
        closeBtn.addEventListener('click', closeBtnHandler);
    }
    
    // Close on Escape key
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            closeModal(modalId);
        }
    };
    document.addEventListener('keydown', escapeHandler);
    
    // Store handlers in WeakMap for cleanup
    modalHandlers.set(modal, {
        escapeHandler,
        overlayHandler,
        closeBtnHandler,
        overlay,
        closeBtn
    });
}

/**
 * Clean up event listeners for the modal
 * @param {HTMLElement} modal - The modal element
 */
function cleanupModalCloseHandlers(modal) {
    const handlers = modalHandlers.get(modal);
    if (!handlers) return;
    
    // Remove escape key handler
    if (handlers.escapeHandler) {
        document.removeEventListener('keydown', handlers.escapeHandler);
    }
    
    // Remove overlay click handler
    if (handlers.overlay && handlers.overlayHandler) {
        handlers.overlay.removeEventListener('click', handlers.overlayHandler);
    }
    
    // Remove close button handler
    if (handlers.closeBtn && handlers.closeBtnHandler) {
        handlers.closeBtn.removeEventListener('click', handlers.closeBtnHandler);
    }
    
    // Remove from WeakMap
    modalHandlers.delete(modal);
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
