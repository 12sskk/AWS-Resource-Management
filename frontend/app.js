let apiUrl = '';
let cognitoDomain = '';
let clientId = '';
let frontendUrl = '';
let idToken = localStorage.getItem('id_token') || '';
let userEmail = localStorage.getItem('user_email') || '';

let currentRole = 'Student';

function updateRole() {
    if (userEmail === 'admin@smartcampus.com') currentRole = 'Admin';
    else if (userEmail.startsWith('faculty') && userEmail.endsWith('@smartcampus.com')) currentRole = 'Faculty';
    else currentRole = 'Student';
}

async function init() {
    // 1. Load dynamic config from S3 (config.json created by CDK)
    try {
        // Cache buster to ensure latest config
        const res = await fetch(`config.json?t=${new Date().getTime()}`);
        const config = await res.json();
        apiUrl = config.apiUrl;
        if (apiUrl.endsWith('/')) apiUrl = apiUrl.slice(0, -1);
        cognitoDomain = config.cognitoDomain;
        clientId = config.clientId;
        frontendUrl = config.frontendUrl;
    } catch (e) {
        console.error("Failed to load config.json. Has it been deployed?", e);
        document.getElementById('loading-screen').innerHTML = '<h2>Error loading config.json. Please deploy the stack.</h2>';
        return;
    }

    // 2. Check for Cognito redirect in URL hash
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);
    if (params.has('id_token')) {
        idToken = params.get('id_token');
        localStorage.setItem('id_token', idToken);
        
        // Decode JWT payload (base64) to get email
        try {
            const payload = JSON.parse(atob(idToken.split('.')[1]));
            userEmail = payload.email || 'User';
            localStorage.setItem('user_email', userEmail);
        } catch(e) { console.error(e); }
        
        // Clear hash from URL to look clean
        window.history.replaceState(null, null, window.location.pathname);
    }

    document.getElementById('loading-screen').style.display = 'none';

    // 3. Setup UI based on auth state
    if (idToken) {
        updateRole();
        document.getElementById('app-main').style.display = 'block';
        document.getElementById('logout-btn').style.display = 'block';
        document.getElementById('user-greeting').innerText = `Hello, ${userEmail} (${currentRole})`;
        checkAdmin();
        loadResources();
        loadBookings();
    } else {
        document.getElementById('login-btn').style.display = 'block';
        document.getElementById('app-main').style.display = 'none';
        document.getElementById('user-greeting').innerText = `Please Login`;
    }
}

function login() {
    const redirect = encodeURIComponent(frontendUrl);
    const authUrl = `${cognitoDomain}/login?client_id=${clientId}&response_type=token&scope=email+openid+profile&redirect_uri=${redirect}`;
    window.location.href = authUrl;
}

function logout() {
    localStorage.removeItem('id_token');
    localStorage.removeItem('user_email');
    window.location.reload();
}

// Wrapper for fetch to include Authorization header
async function apiFetch(path, options = {}) {
    if (!options.headers) options.headers = {};
    options.headers['Authorization'] = idToken;
    options.headers['Content-Type'] = 'application/json';
    
    const res = await fetch(`${apiUrl}${path}`, options);
    if (res.status === 401 || res.status === 403) {
        alert("Session expired or unauthorized. Please login again.");
        logout();
    }
    return res;
}

function checkAdmin() {
    const adminDiv = document.getElementById('add-resource-form');
    if (currentRole === 'Admin') {
        adminDiv.style.display = 'block';
    } else {
        adminDiv.style.display = 'none';
    }
}

async function loadResources() {
    try {
        const res = await apiFetch('/resources');
        const data = await res.json();
        
        const list = document.getElementById('resources-list');
        const select = document.getElementById('book-resource');
        list.innerHTML = '';
        select.innerHTML = '<option value="">Select Resource...</option>';
        
        data.forEach(item => {
            list.innerHTML += `
                <div class="list-item">
                    <strong>${item.Name}</strong> (${item.Type})<br>
                    Capacity: ${item.Capacity} | Status: ${item.Status}
                </div>
            `;
            select.innerHTML += `<option value="${item.ResourceId}">${item.Name} (${item.Type})</option>`;
        });
    } catch (e) {
        console.error(e);
    }
}

async function addResource() {
    const name = document.getElementById('res-name').value;
    const type = document.getElementById('res-type').value;
    const capacity = parseInt(document.getElementById('res-capacity').value);
    
    try {
        await apiFetch('/resources', {
            method: 'POST',
            body: JSON.stringify({ name, type, capacity })
        });
        alert('Resource added!');
        loadResources();
    } catch (e) {
        console.error(e);
    }
}

async function submitBooking(e) {
    e.preventDefault();
    
    const resourceId = document.getElementById('book-resource').value;
    const startTime = document.getElementById('book-start').value;
    const endTime = document.getElementById('book-end').value;
    const purpose = document.getElementById('book-purpose').value;
    const requiredCapacity = document.getElementById('book-capacity').value;
    
    const startIso = new Date(startTime).toISOString();
    const endIso = new Date(endTime).toISOString();
    
    try {
        const res = await apiFetch('/bookings', {
            method: 'POST',
            body: JSON.stringify({ 
                resourceId, 
                startTime: startIso, 
                endTime: endIso, 
                purpose,
                requiredCapacity
            })
        });
        
        const data = await res.json();
        const msgEl = document.getElementById('booking-message');
        if (res.ok) {
            msgEl.innerHTML = `<span style="color:green">${data.message}. Status: ${data.Status}</span>`;
            loadBookings();
        } else {
            msgEl.innerHTML = `<span style="color:red">Error: ${data.message}</span>`;
        }
    } catch (e) {
        console.error(e);
    }
}

async function loadBookings() {
    try {
        const res = await apiFetch('/bookings');
        const data = await res.json();
        
        const list = document.getElementById('bookings-list');
        list.innerHTML = '';
        
        data.forEach(item => {
            let badgeClass = 'bg-warning';
            if (item.Status === 'Approved') badgeClass = 'bg-success';
            if (item.Status === 'Rejected' || item.Status === 'Cancelled') badgeClass = 'bg-danger';
            
            let html = `
                <div class="list-item">
                    <strong>User:</strong> ${item.UserId}<br>
                    <strong>Booking ID:</strong> ${item.BookingId.substring(0,8)}...<br>
                    <strong>Time:</strong> ${new Date(item.StartTime).toLocaleString()} to ${new Date(item.EndTime).toLocaleString()}<br>
                    <strong>Capacity Booked:</strong> ${item.RequiredCapacity || 1}<br>
                    <strong>Status:</strong> <span class="badge ${badgeClass}">${item.Status}</span>
                    <br><strong>Role:</strong> ${item.Role}
            `;
            
            if (item.Status === 'Pending' && (currentRole === 'Admin' || currentRole === 'Faculty')) {
                html += `
                    <div class="action-btns">
                        <button class="bg-success" onclick="updateBooking('${item.BookingId}', 'Approved')">Approve</button>
                        <button class="bg-danger" onclick="updateBooking('${item.BookingId}', 'Rejected')">Reject</button>
                    </div>
                `;
            }
            html += `</div>`;
            list.innerHTML += html;
        });
    } catch (e) {
        console.error(e);
    }
}

async function updateBooking(bookingId, status) {
    try {
        await apiFetch(`/bookings/${bookingId}`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        loadBookings();
    } catch(e) {
        console.error(e);
    }
}

// Start application
init();
