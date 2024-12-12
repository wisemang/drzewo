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
    // Initialize the map with a default view (will be updated by geolocation)
    map = L.map('map', {
        fullscreenControl: true, // Enable fullscreen control
        fullscreenControlOptions: {
            position: 'topleft' // Place it in the top-left corner
        }
    }).setView([43.65107, -79.347015], 13);

    // Attach event listeners
    map.on('zoomend', onMapInteraction);
    map.on('moveend', onMapInteraction);

    // Define the OSM layer
    osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 21
    });

    // Define the OpenFreeMap layer using MapLibre GL
    openFreeMapLayer = L.maplibreGL({
        attribution: '© OpenStreetMap contributors, OpenFreeMap',
        style: 'https://tiles.openfreemap.org/styles/liberty',
    });

    // Add the default layer to the map
    // map.addLayer(osmLayer);
    map.addLayer(openFreeMapLayer);

    // Center map to user's location on load
    getLocation();
}

let debounceTimer;
let lastLoadedCenter = null;
let lastZoomLevel = null;
const maxMarkers = 200;

function onMapInteraction() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        const currentCenter = map.getCenter();
        const currentZoom = map.getZoom();

        const distanceThreshold = 100; // Meters
        const zoomThreshold = 2;

        if (
            !lastLoadedCenter ||
            currentCenter.distanceTo(lastLoadedCenter) > distanceThreshold ||
            Math.abs(currentZoom - lastZoomLevel) >= zoomThreshold
        ) {
            lastLoadedCenter = currentCenter;
            lastZoomLevel = currentZoom;
            fetchTrees(currentCenter.lat, currentCenter.lng);
        }
    }, 300); // Debounce delay
}

// Toggle between OSM and OpenFreeMap
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


// Use Geolocation API to center map on user's location
function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => displayLocation(position),
            error => showError(error)
        );
    } else {
        document.getElementById('location').textContent = "Geolocation is not supported by this browser.";
    }
}

function displayLocation(position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    const accuracy = position.coords.accuracy;

    document.getElementById('location').textContent = `Latitude: ${latitude}, Longitude: ${longitude}`;
    document.getElementById('accuracy').textContent = `Accuracy: ±${accuracy.toFixed(1)} meters`;

    // Update the map view
    map.setView([latitude, longitude], 19);

    // Add or update the user's location marker
    if (!userMarker) {
        userMarker = L.marker([latitude, longitude]).addTo(map).bindPopup("You are here");
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
    while (treeMarkers.length > maxMarkers) {
        const marker = treeMarkers.shift();
        map.removeLayer(marker);
    }

    data.forEach((item, index) => {
        const marker = L.marker([item.latitude, item.longitude], { icon: treeIcon }).addTo(map);

        const popupContent = `
            <div class="tree-marker">
                <span class="tree-marker-common-name">${item.common_name}</span><br>
                <span class="tree-marker-address">${item.address} ${item.streetname}</span><br>
                <hr>
                <table class="treedata">
                    <tr><td>Botanical name</td><td>${item.botanical_name}</td></tr>
                    <tr><td>Diameter at breast height</td><td>${item.dbh} cm</td></tr>
                </table>
            </div>
        `;

        marker.bindPopup(popupContent);

        // Add the marker to the global array
        treeMarkers.push(marker);

        // Highlight the corresponding row when the marker is clicked
        marker.on('click', () => highlightRow(index));
    });
}

function highlightMarker(index) {
    const marker = treeMarkers[index];
    if (marker) {
        map.setView(marker.getLatLng(), 18); // Center the map on the marker
        marker.openPopup();
        highlightRow(index);
    }
}

function highlightRow(index) {
    document.querySelectorAll('tr').forEach(row => row.classList.remove('highlight')); // Remove existing highlights
    const row = document.getElementById(`tree-row-${index}`);
    if (row) row.classList.add('highlight'); // Add highlight to the clicked row
}

function updateTable(data) {
    const tableBody = document.getElementById('resultsTable').querySelector('tbody');
    tableBody.innerHTML = '';

    data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.id = `tree-row-${index}`;
        row.innerHTML = `
            <td>${item.address} ${item.streetname}</td>
            <td>${item.common_name}</td>
            <td>${item.botanical_name}</td>
            <td>${item.dbh}</td>
            <td>${item.distance.toFixed(2)}</td>
        `;

        // Add click event to highlight the marker
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

    // Add Event Listeners
    document.getElementById('current-location').addEventListener('click', getLocation);
    document.getElementById('load-more-trees').addEventListener('click', getTreesAtCenter);
}

// Initialize the map and load location
initializeMap();
addCustomControls();

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
});
