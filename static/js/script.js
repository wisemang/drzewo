let map; // Global map instance
let userMarker; // User marker
let treeMarkers = []; // Array to store tree markers
let currentProvider = 'openfreemap'; // Default map provider
let osmLayer, openFreeMapLayer;

// Custom tree icon
const treeIcon = L.icon({
    iconUrl: 'static/images/tree-gross-outline-svgrepo-com.svg',
    iconSize: [30, 30],
    iconAnchor: [15, 30],
    popupAnchor: [0, -30]
});

function initializeMap() {
    map = L.map('map').setView([43.65107, -79.347015], 13);

    // Just keep the essential event listeners for tree loading
    map.on('moveend', onMapInteraction);
    map.on('zoomend', onMapInteraction);

    osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 21
    });

    openFreeMapLayer = L.maplibreGL({
        attribution: '© OpenStreetMap contributors, OpenFreeMap',
        style: 'https://tiles.openfreemap.org/styles/liberty',
        interactive: true,  // Keep interactions enabled
        dragRotate: false,  // Keep 3D rotation disabled
        pitchWithRotate: false,
        inertia: false,     // Disable inertial scrolling
        dragPan: {
            inertia: false  // Also disable inertia in drag-pan
        },
        pane: 'tilePane'    // Keep the layer in the tile pane
    });
    
    // Create a separate pane for markers to ensure proper layering
    map.createPane('markerPane');
    map.getPane('markerPane').style.zIndex = 600;

    map.addLayer(osmLayer);
    
    // Get initial location
    getLocation();
}

let debounceTimer;
let lastLoadedCenter = null;
let lastZoomLevel = null;
const maxMarkers = 200;
let isMapFullscreen = false;
const FULLSCREEN_ENTER_ICON = '⛶';
const FULLSCREEN_EXIT_ICON = `
<svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-hidden="true">
  <path d="M5.5 0a.5.5 0 0 1 .5.5v4A1.5 1.5 0 0 1 4.5 6h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 1 .5-.5zm5 0a.5.5 0 0 1 .5.5v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 1 0 1h-4A1.5 1.5 0 0 1 10 4.5v-4a.5.5 0 0 1 .5-.5zM0 10.5a.5.5 0 0 1 .5-.5h4A1.5 1.5 0 0 1 6 11.5v4a.5.5 0 0 1-1 0v-4a.5.5 0 0 0-.5-.5h-4a.5.5 0 0 1-.5-.5zm10 1a1.5 1.5 0 0 1 1.5-1.5h4a.5.5 0 0 1 0 1h-4a.5.5 0 0 0-.5.5v4a.5.5 0 0 1-1 0v-4z"/>
</svg>`;

function onMapInteraction() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        const currentCenter = map.getCenter();
        const currentZoom = map.getZoom();

        // Store new center and zoom level
        if (!lastLoadedCenter) {
            lastLoadedCenter = currentCenter;
            lastZoomLevel = currentZoom;
        }

        const distanceThreshold = 100; // Meters
        const zoomThreshold = 2;

        // Only fetch new trees if we've moved significantly
        if (currentCenter.distanceTo(lastLoadedCenter) > distanceThreshold ||
            Math.abs(currentZoom - lastZoomLevel) >= zoomThreshold) {
            lastLoadedCenter = currentCenter;
            lastZoomLevel = currentZoom;
            fetchTrees(currentCenter.lat, currentCenter.lng);
        }
    }, 300); // Debounce delay
}

function toggleMapProvider() {
    if (currentProvider === 'osm') {
        map.removeLayer(osmLayer);
        map.addLayer(openFreeMapLayer);
        currentProvider = 'openfreemap';
        document.getElementById('toggle-provider').textContent = 'Switch to OSM';
    } else {
        map.removeLayer(openFreeMapLayer);
        map.addLayer(osmLayer);
        currentProvider = 'osm';
        document.getElementById('toggle-provider').textContent = 'Switch to OpenFreeMap';
    }
}

function getTreesAtCenter() {
    const center = map.getCenter();
    fetchTrees(center.lat, center.lng);
}

function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => displayLocation(position, true),
            error => showError(error),
            { enableHighAccuracy: true }
        );
    } else {
        document.getElementById('location').textContent = "Geolocation is not supported by this browser.";
    }
}

function displayLocation(position, centerMap = false) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    const accuracy = position.coords.accuracy;

    document.getElementById('location').textContent = `Latitude: ${latitude}, Longitude: ${longitude}`;
    document.getElementById('accuracy').textContent = `Accuracy: ±${accuracy.toFixed(1)} meters`;

    // Only set view on initial location or when explicitly requested
    if (!userMarker || centerMap) {
        map.setView([latitude, longitude], 19);
    }

    // Add or update the user's location marker
    if (!userMarker) {
        userMarker = L.marker([latitude, longitude], {
            pane: 'markerPane'
        }).addTo(map).bindPopup("You are here");
    } else {
        userMarker.setLatLng([latitude, longitude]);
    }

    // Fetch nearby trees
    fetchTrees(latitude, longitude);
}

function showError(error) {
    let message = "An unknown error occurred.";
    switch (error.code) {
        case error.PERMISSION_DENIED:
            message = "User denied the request for Geolocation.";
            break;
        case error.POSITION_UNAVAILABLE:
            message = "Location information is unavailable.";
            break;
        case error.TIMEOUT:
            message = "The request to get user location timed out.";
            break;
    }
    document.getElementById('location').textContent = message;
}

function fetchTrees(latitude, longitude) {
    fetch(`/nearest?lat=${latitude}&lng=${longitude}&limit=40`)
        .then(response => response.json())
        .then(data => {
            updateTable(data);
            addMarkers(data);
        })
        .catch(error => console.error('Error fetching data:', error));
}

function addMarkers(data) {
    // Clear old markers if we're over the limit
    while (treeMarkers.length > maxMarkers) {
        const marker = treeMarkers.shift();
        map.removeLayer(marker);
    }

    data.forEach((item, index) => {
        const marker = L.marker([item.latitude, item.longitude], { 
            icon: treeIcon,
            pane: 'markerPane'
        }).addTo(map);

        const dbhDisplay = item.dbh ? `${item.dbh} cm` : 'N/A';
        const addressDisplay = item.streetname ? `${item.address} ${item.streetname}` : item.address;

        const popupContent = `
            <div class="tree-marker">
                <span class="tree-marker-common-name">${item.common_name}</span><br>
                <span class="tree-marker-address">${addressDisplay}</span><br>
                <hr>
                <table class="treedata">
                    <tr><td>Botanical name</td><td>${item.botanical_name}</td></tr>
                    <tr><td>Diameter</td><td>${dbhDisplay}</td></tr>
                </table>
            </div>
        `;

        marker.bindPopup(popupContent);
        treeMarkers.push(marker);
        marker.on('click', () => highlightRow(index));
    });
}

function highlightMarker(index) {
    const marker = treeMarkers[index];
    if (marker) {
        // Use panTo instead of setView to maintain zoom level
        map.panTo(marker.getLatLng());
        marker.openPopup();
        highlightRow(index);
    }
}

function highlightRow(index) {
    document.querySelectorAll('tr').forEach(row => row.classList.remove('highlight'));
    const row = document.getElementById(`tree-row-${index}`);
    if (row) row.classList.add('highlight');
}

function updateTable(data) {
    const tableBody = document.getElementById('resultsTable').querySelector('tbody');
    tableBody.innerHTML = '';

    data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.id = `tree-row-${index}`;
        const addressDisplay = item.streetname ? `${item.address} ${item.streetname}` : item.address;
        
        row.innerHTML = `
            <td>${addressDisplay}</td>
            <td>${item.common_name}</td>
            <td>${item.botanical_name}</td>
            <td>${item.dbh ? item.dbh : 'N/A'}</td>
            <td>${item.distance.toFixed(2)}</td>
        `;

        row.addEventListener('click', () => highlightMarker(index));
        tableBody.appendChild(row);
    });
}

function addCustomControls() {
    // Current Location Button
    const currentLocationControl = L.control({ position: 'topleft' });
    currentLocationControl.onAdd = function () {
        const div = L.DomUtil.create('div', 'leaflet-control leaflet-control-custom');
        div.innerHTML = `<button id="current-location" class="map-icon-button" title="Go to current location">📍</button>`;
        return div;
    };
    currentLocationControl.addTo(map);

    // Load More Trees Button
    const loadTreesControl = L.control({ position: 'topleft' });
    loadTreesControl.onAdd = function () {
        const div = L.DomUtil.create('div', 'leaflet-control leaflet-control-custom');
        div.innerHTML = `<button id="load-more-trees" class="map-icon-button" title="Load more trees">🌳</button>`;
        return div;
    };
    loadTreesControl.addTo(map);

    // Fullscreen Map Mode Button
    const mapFullscreenControl = L.control({ position: 'topleft' });
    mapFullscreenControl.onAdd = function () {
        const div = L.DomUtil.create('div', 'leaflet-control leaflet-control-custom');
        div.innerHTML = `<button id="toggle-map-fullscreen" class="map-icon-button" title="Enter fullscreen map" aria-label="Enter fullscreen map">${FULLSCREEN_ENTER_ICON}</button>`;
        return div;
    };
    mapFullscreenControl.addTo(map);

    // Add Event Listeners
    document.getElementById('current-location').addEventListener('click', getLocation);
    document.getElementById('load-more-trees').addEventListener('click', getTreesAtCenter);
    document.getElementById('toggle-map-fullscreen').addEventListener('click', () => {
        setMapFullscreen(!isMapFullscreen);
    });
}

function setMapFullscreen(enabled) {
    isMapFullscreen = enabled;
    document.body.classList.toggle('map-fullscreen-active', enabled);

    const button = document.getElementById('toggle-map-fullscreen');
    if (button) {
        if (enabled) {
            button.innerHTML = FULLSCREEN_EXIT_ICON;
        } else {
            button.textContent = FULLSCREEN_ENTER_ICON;
        }
        button.title = enabled ? 'Exit fullscreen map' : 'Enter fullscreen map';
        button.setAttribute('aria-label', button.title);
    }

    setTimeout(() => {
        map.invalidateSize();
    }, 50);
}

// Initialize the map and load location
initializeMap();
addCustomControls();

// Menu handling
document.addEventListener('DOMContentLoaded', () => {
    const homeLink = document.getElementById('home-link');
    const aboutLink = document.getElementById('about-link');
    const homePage = document.getElementById('home-page');
    const aboutPage = document.getElementById('about-page');

    const menuIcon = document.querySelector('.menu-icon');
    const menuDropdown = document.querySelector('.menu-dropdown');
    const menuLinks = menuDropdown.querySelectorAll('a');

    menuIcon.addEventListener('click', () => {
        menuDropdown.classList.toggle('show');
    });
    
    menuLinks.forEach(link => {
        link.addEventListener('click', () => {
            menuDropdown.classList.remove('show');
        });
    });

    function switchPage(target) {
        if (target !== 'home' && isMapFullscreen) {
            setMapFullscreen(false);
        }
        if (target === 'home') {
            homePage.style.display = 'block';
            aboutPage.style.display = 'none';
            homeLink.classList.add('active');
            aboutLink.classList.remove('active');
        } else if (target === 'about') {
            homePage.style.display = 'none';
            aboutPage.style.display = 'block';
            aboutLink.classList.add('active');
            homeLink.classList.remove('active');
        }
    }

    homeLink.addEventListener('click', (e) => {
        e.preventDefault();
        switchPage('home');
    });

    aboutLink.addEventListener('click', (e) => {
        e.preventDefault();
        switchPage('about');
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && isMapFullscreen) {
            setMapFullscreen(false);
        }
    });
});
