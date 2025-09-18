// Global error handling
document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Handle logout
    document.getElementById('logoutBtn')?.addEventListener('click', function() {
        fetch('/logout', { method: 'GET' })
            .then(() => window.location.href = '/login');
    });
});

// API helper function
async function makeApiRequest(url, method = 'GET', body = null) {
    const token = localStorage.getItem('access_token') || 
                 document.cookie.split('; ').find(row => row.startsWith('access_token='))?.split('=')[1];
    
    const headers = {
        'Content-Type': 'application/json',
    };
    
    if (token) {
        headers['Authorization'] = token;
    }

    const options = {
        method,
        headers,
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
    }

    return response.json();
}