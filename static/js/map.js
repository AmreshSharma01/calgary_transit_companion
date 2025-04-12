// Map handling functions for Calgary Transit App

// Initialize map variables
let map;
let vehicleMarkers = [];
let routeLines = [];
let stopMarkers = [];
let selectedRouteId = null;

// Vehicle icon by crowding level
const vehicleIcons = {
  low: L.divIcon({
    html: '<i class="fas fa-bus" style="color:#28a745;font-size:20px;"></i>',
    className: "vehicle-marker-icon",
    iconSize: [20, 20],
  }),
  medium: L.divIcon({
    html: '<i class="fas fa-bus" style="color:#ffc107;font-size:20px;"></i>',
    className: "vehicle-marker-icon",
    iconSize: [20, 20],
  }),
  high: L.divIcon({
    html: '<i class="fas fa-bus" style="color:#dc3545;font-size:20px;"></i>',
    className: "vehicle-marker-icon",
    iconSize: [20, 20],
  }),
  unknown: L.divIcon({
    html: '<i class="fas fa-bus" style="color:#6c757d;font-size:20px;"></i>',
    className: "vehicle-marker-icon",
    iconSize: [20, 20],
  }),
};

// Stop icon
const stopIcon = L.divIcon({
  html: '<i class="fas fa-circle" style="color:#007bff;font-size:10px;"></i>',
  className: "stop-marker-icon",
  iconSize: [10, 10],
});

// Initialize the map
function initMap(centerLat, centerLng, zoom) {
  // Create map if it doesn't exist yet
  if (!map) {
    map = L.map("map").setView([centerLat, centerLng], zoom);

    // Add dark mode tile layer (Stadia Maps Dark)
    L.tileLayer(
      "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 20,
        attribution:
          '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors',
      }
    ).addTo(map);

    // Add geolocation control
    L.control
      .locate({
        position: "topright",
        icon: "fas fa-location-arrow",
        flyTo: true,
        cacheLocation: true,
        showPopup: false,
        strings: {
          title: "Show me where I am",
        },
      })
      .addTo(map);

    // Add scale control
    L.control.scale({ imperial: false }).addTo(map);
  } else {
    // If map exists, just update the view
    map.setView([centerLat, centerLng], zoom);
  }

  // Initialize or refresh real-time updates
  startRealtimeUpdates();
}

// Load and display real-time vehicle positions
function loadVehiclePositions() {
  fetch("/api/vehicles")
    .then((response) => response.json())
    .then((vehicles) => {
      // Clear existing vehicle markers
      clearVehicleMarkers();

      // Add new markers
      vehicles.forEach((vehicle) => {
        if (vehicle.latitude && vehicle.longitude) {
          // Skip if not related to selected route
          if (selectedRouteId && vehicle.route_id !== selectedRouteId) {
            return;
          }

          // Determine crowding level
          let crowdingLevel = "unknown";
          if (vehicle.occupancy_status) {
            if (vehicle.occupancy_status <= 1) crowdingLevel = "low";
            else if (vehicle.occupancy_status <= 4) crowdingLevel = "medium";
            else crowdingLevel = "high";
          }

          // Create marker
          const marker = L.marker([vehicle.latitude, vehicle.longitude], {
            icon: vehicleIcons[crowdingLevel],
            rotationAngle: vehicle.bearing || 0,
            rotationOrigin: "center",
          });

          // Create popup content
          const timestamp = vehicle.timestamp
            ? new Date(vehicle.timestamp * 1000).toLocaleTimeString()
            : "Unknown";
          const statusText = getStatusText(vehicle.current_status);
          const crowdingText = getCrowdingText(vehicle.occupancy_status);

          let popupContent = `
            <div class="vehicle-popup">
              <div class="route-number">${vehicle.route_id || "Unknown"}</div>
              <div>Status: ${statusText}</div>
              <div>Crowding: ${crowdingText}</div>
              <div class="vehicle-info">Last updated: ${timestamp}</div>
            </div>
          `;

          marker.bindPopup(popupContent);
          marker.addTo(map);
          vehicleMarkers.push(marker);
        }
      });
    })
    .catch((error) => {
      console.error("Error fetching vehicle positions:", error);
    });
}

// Convert vehicle status to readable text
function getStatusText(status) {
  switch (status) {
    case 0:
      return "Incoming at stop";
    case 1:
      return "Stopped at stop";
    case 2:
      return "In transit to stop";
    default:
      return "Unknown";
  }
}

// Convert occupancy status to readable text
function getCrowdingText(status) {
  switch (status) {
    case 0:
      return "Empty";
    case 1:
      return "Many seats available";
    case 2:
      return "Few seats available";
    case 3:
      return "Standing room only";
    case 4:
      return "Crushed standing room only";
    case 5:
      return "Full";
    case 6:
      return "Not accepting passengers";
    default:
      return "Unknown";
  }
}

// Display route details on the map
function displayRoute(routeId) {
  // Clear previous route
  clearRouteDisplay();

  // Set selected route
  selectedRouteId = routeId;

  // Fetch route details
  fetch(`/api/route/${routeId}`)
    .then((response) => response.json())
    .then((data) => {
      // Extract route and shape data
      const route = data.route;
      const shapes = data.shapes;

      // Display route name in overlay
      const routeOverlay = document.getElementById("route-overlay");
      if (routeOverlay) {
        routeOverlay.textContent = `Route ${route.route_short_name}: ${route.route_long_name}`;
        routeOverlay.style.display = "block";
      }

      // Display shapes on map
      for (const shapeId in shapes) {
        const points = shapes[shapeId];
        if (points && points.length > 0) {
          const latlngs = points.map((p) => [p.lat, p.lng]);
          const routeLine = L.polyline(latlngs, {
            color: "#0078d4",
            weight: 4,
            opacity: 0.8,
          }).addTo(map);
          routeLines.push(routeLine);

          // Fit map to route
          map.fitBounds(routeLine.getBounds(), { padding: [50, 50] });
        }
      }

      // Fetch stops for this route
      fetchRouteStops(routeId);

      // Load vehicles again to filter by route
      loadVehiclePositions();
    })
    .catch((error) => {
      console.error("Error fetching route details:", error);
    });
}

// Fetch and display stops for a route
function fetchRouteStops(routeId) {
  // Typically this would be a separate API endpoint, but for now we'll simplify
  // This would ideally fetch stops for the specific route

  // For demonstration, we'll just display nearby stops
  if (map.getCenter()) {
    const center = map.getCenter();
    fetch(`/api/nearby_stops?lat=${center.lat}&lon=${center.lng}&radius=5`)
      .then((response) => response.json())
      .then((stops) => {
        stops.forEach((stop) => {
          const marker = L.marker([stop.stop_lat, stop.stop_lon], {
            icon: stopIcon,
          });

          marker.bindPopup(
            `<b>${stop.stop_name}</b><br>Stop ID: ${stop.stop_id}`
          );
          marker.addTo(map);
          stopMarkers.push(marker);
        });
      })
      .catch((error) => {
        console.error("Error fetching stops:", error);
      });
  }
}

// Clear all vehicle markers from the map
function clearVehicleMarkers() {
  vehicleMarkers.forEach((marker) => {
    map.removeLayer(marker);
  });
  vehicleMarkers = [];
}

// Clear route display (lines and stops)
function clearRouteDisplay() {
  // Remove route lines
  routeLines.forEach((line) => {
    map.removeLayer(line);
  });
  routeLines = [];

  // Remove stop markers
  stopMarkers.forEach((marker) => {
    map.removeLayer(marker);
  });
  stopMarkers = [];

  // Hide route overlay
  const routeOverlay = document.getElementById("route-overlay");
  if (routeOverlay) {
    routeOverlay.style.display = "none";
  }

  // Reset selected route
  selectedRouteId = null;
}

// Start periodic real-time updates
function startRealtimeUpdates() {
  // Load initial vehicle positions
  loadVehiclePositions();

  // Set up periodic refresh (every 30 seconds)
  if (window.vehicleUpdateInterval) {
    clearInterval(window.vehicleUpdateInterval);
  }
  window.vehicleUpdateInterval = setInterval(loadVehiclePositions, 30000);
}

// Use user's location to find nearby stops
function findNearbyStops() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;

        // Center map on user's location
        map.setView([lat, lon], 15);

        // Add user marker
        L.marker([lat, lon], {
          icon: L.divIcon({
            html: '<i class="fas fa-user-circle" style="color:#17a2b8;font-size:24px;"></i>',
            className: "user-marker-icon",
            iconSize: [24, 24],
          }),
        }).addTo(map);

        // Fetch nearby stops
        fetch(`/api/nearby_stops?lat=${lat}&lon=${lon}&radius=0.5`)
          .then((response) => response.json())
          .then((stops) => {
            stops.forEach((stop) => {
              const marker = L.marker([stop.stop_lat, stop.stop_lon], {
                icon: stopIcon,
              });

              marker.bindPopup(`
              <b>${stop.stop_name}</b><br>
              Stop ID: ${stop.stop_id}<br>
              Distance: ${stop.distance} km
            `);
              marker.addTo(map);
              stopMarkers.push(marker);
            });

            if (stops.length > 0) {
              // Show a message in the overlay
              const routeOverlay = document.getElementById("route-overlay");
              if (routeOverlay) {
                routeOverlay.textContent = `Found ${stops.length} stops nearby`;
                routeOverlay.style.display = "block";

                // Hide after 5 seconds
                setTimeout(() => {
                  routeOverlay.style.display = "none";
                }, 5000);
              }
            }
          })
          .catch((error) => {
            console.error("Error fetching nearby stops:", error);
          });
      },
      (error) => {
        console.error("Geolocation error:", error);
        alert("Could not get your location. Please enable location services.");
      }
    );
  } else {
    alert("Geolocation is not supported by your browser.");
  }
}

// Utility function to create a search from map click
function setSearchPoint(type, latlng) {
  if (type === "start") {
    if (document.getElementById("start_lat")) {
      document.getElementById("start_lat").value = latlng.lat.toFixed(6);
    }
    if (document.getElementById("start_lon")) {
      document.getElementById("start_lon").value = latlng.lng.toFixed(6);
    }
  } else if (type === "end") {
    if (document.getElementById("end_lat")) {
      document.getElementById("end_lat").value = latlng.lat.toFixed(6);
    }
    if (document.getElementById("end_lon")) {
      document.getElementById("end_lon").value = latlng.lng.toFixed(6);
    }
  }
}

// Map click handler for search page
function initSearchMapClicks() {
  if (map) {
    // Create start and end markers
    const startMarker = L.marker([0, 0], {
      icon: L.divIcon({
        html: '<i class="fas fa-play-circle" style="color:#28a745;font-size:24px;"></i>',
        className: "start-marker-icon",
        iconSize: [24, 24],
      }),
      draggable: true,
    });

    const endMarker = L.marker([0, 0], {
      icon: L.divIcon({
        html: '<i class="fas fa-flag-checkered" style="color:#dc3545;font-size:24px;"></i>',
        className: "end-marker-icon",
        iconSize: [24, 24],
      }),
      draggable: true,
    });

    // Setup map click handler
    map.on("click", function (e) {
      const activeBtn = document.querySelector(".point-select-btn.active");
      if (activeBtn) {
        const pointType = activeBtn.dataset.point;

        if (pointType === "start") {
          startMarker.setLatLng(e.latlng);
          if (!startMarker._map) startMarker.addTo(map);
          setSearchPoint("start", e.latlng);
        } else if (pointType === "end") {
          endMarker.setLatLng(e.latlng);
          if (!endMarker._map) endMarker.addTo(map);
          setSearchPoint("end", e.latlng);
        }
      }
    });

    // Setup marker drag handlers
    startMarker.on("dragend", function (e) {
      setSearchPoint("start", startMarker.getLatLng());
    });

    endMarker.on("dragend", function (e) {
      setSearchPoint("end", endMarker.getLatLng());
    });
  }
}
