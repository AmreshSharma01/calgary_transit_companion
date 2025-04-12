// Search functionality for Calgary Transit App

// Initialize search form functionality
function initSearchForm() {
  // Set up point selection buttons
  const pointButtons = document.querySelectorAll(".point-select-btn");
  pointButtons.forEach((btn) => {
    btn.addEventListener("click", function () {
      // Remove active class from all buttons
      pointButtons.forEach((b) => b.classList.remove("active"));

      // Add active class to clicked button
      this.classList.add("active");

      // Show instruction
      const instructionElement = document.getElementById("map-instruction");
      if (instructionElement) {
        const pointType =
          this.dataset.point === "start" ? "starting" : "destination";
        instructionElement.textContent = `Click on the map to set your ${pointType} point`;
        instructionElement.style.display = "block";
      }
    });
  });

  // Set up time option change handlers
  const timeSelect = document.getElementById("departure_time");
  const customTimeContainer = document.getElementById("custom_time_container");

  if (timeSelect && customTimeContainer) {
    timeSelect.addEventListener("change", function () {
      if (this.value === "custom") {
        customTimeContainer.style.display = "block";
      } else {
        customTimeContainer.style.display = "none";
      }
    });
  }

  // Set up form validation
  const searchForm = document.getElementById("route-search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", function (e) {
      const startLat = document.getElementById("start_lat").value;
      const startLon = document.getElementById("start_lon").value;
      const endLat = document.getElementById("end_lat").value;
      const endLon = document.getElementById("end_lon").value;

      if (!startLat || !startLon || !endLat || !endLon) {
        e.preventDefault();
        alert("Please select both starting and destination points on the map.");
      }
    });
  }

  // Set up geolocation for current location
  const useCurrentLocationBtn = document.getElementById("use-current-location");
  if (useCurrentLocationBtn) {
    useCurrentLocationBtn.addEventListener("click", function () {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          function (position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            // Set form values
            document.getElementById("start_lat").value = lat.toFixed(6);
            document.getElementById("start_lon").value = lon.toFixed(6);

            // Add marker to map
            if (map) {
              // Center on user location
              map.setView([lat, lon], 15);

              // Show marker
              const userMarker = L.marker([lat, lon], {
                icon: L.divIcon({
                  html: '<i class="fas fa-play-circle" style="color:#28a745;font-size:24px;"></i>',
                  className: "start-marker-icon",
                  iconSize: [24, 24],
                }),
              }).addTo(map);

              // Store marker for later use
              window.userMarker = userMarker;
            }
          },
          function (error) {
            console.error("Geolocation error:", error);
            alert(
              "Could not get your location. Please enable location services or set your location on the map."
            );
          }
        );
      } else {
        alert("Geolocation is not supported by your browser.");
      }
    });
  }

  // Initialize destination search from points of interest
  initDestinationSearch();
}

// Initialize autocomplete for destination search
function initDestinationSearch() {
  const destinationInput = document.getElementById("destination-search");
  const suggestionsContainer = document.getElementById(
    "destination-suggestions"
  );

  if (!destinationInput || !suggestionsContainer) return;

  // Common destinations in Calgary
  const popularDestinations = [
    { name: "University of Calgary", lat: 51.0766, lon: -114.1333 },
    { name: "Calgary Zoo", lat: 51.0455, lon: -114.0023 },
    { name: "Chinook Centre", lat: 50.998, lon: -114.073 },
    { name: "Calgary Tower", lat: 51.0442, lon: -114.0631 },
    { name: "Foothills Medical Centre", lat: 51.0644, lon: -114.132 },
    { name: "SAIT", lat: 51.0655, lon: -114.0911 },
    { name: "Calgary International Airport", lat: 51.1284, lon: -114.0133 },
    { name: "Stampede Park", lat: 51.0381, lon: -114.0591 },
    { name: "Downtown Calgary", lat: 51.0464, lon: -114.0652 },
    { name: "Heritage Park", lat: 50.9829, lon: -114.1108 },
  ];

  destinationInput.addEventListener("input", function () {
    const query = this.value.toLowerCase();

    if (query.length < 2) {
      suggestionsContainer.style.display = "none";
      return;
    }

    // Filter destinations
    const matches = popularDestinations.filter((dest) =>
      dest.name.toLowerCase().includes(query)
    );

    // Show suggestions
    if (matches.length > 0) {
      suggestionsContainer.innerHTML = "";
      matches.forEach((dest) => {
        const item = document.createElement("div");
        item.className = "suggestion-item";
        item.innerHTML = `<i class="fas fa-map-marker-alt me-2"></i>${dest.name}`;

        item.addEventListener("click", function () {
          // Set the destination coordinates
          document.getElementById("end_lat").value = dest.lat.toFixed(6);
          document.getElementById("end_lon").value = dest.lon.toFixed(6);

          // Update input field
          destinationInput.value = dest.name;

          // Hide suggestions
          suggestionsContainer.style.display = "none";

          // Update map
          if (map) {
            // Add marker
            if (window.destMarker) {
              map.removeLayer(window.destMarker);
            }

            window.destMarker = L.marker([dest.lat, dest.lon], {
              icon: L.divIcon({
                html: '<i class="fas fa-flag-checkered" style="color:#dc3545;font-size:24px;"></i>',
                className: "end-marker-icon",
                iconSize: [24, 24],
              }),
            }).addTo(map);

            // Center map between start and end if start point exists
            const startLat = parseFloat(
              document.getElementById("start_lat").value
            );
            const startLon = parseFloat(
              document.getElementById("start_lon").value
            );

            if (startLat && startLon) {
              const bounds = L.latLngBounds(
                [startLat, startLon],
                [dest.lat, dest.lon]
              );
              map.fitBounds(bounds, { padding: [50, 50] });
            } else {
              map.setView([dest.lat, dest.lon], 15);
            }
          }
        });

        suggestionsContainer.appendChild(item);
      });

      suggestionsContainer.style.display = "block";
    } else {
      suggestionsContainer.style.display = "none";
    }
  });

  // Hide suggestions when clicking outside
  document.addEventListener("click", function (e) {
    if (e.target !== destinationInput && e.target !== suggestionsContainer) {
      suggestionsContainer.style.display = "none";
    }
  });
}

// Format a route for display
function formatRouteDisplay(route) {
  // Handle different route types
  if (route.type === "direct") {
    return formatDirectRoute(route);
  } else if (route.type === "transfer") {
    return formatTransferRoute(route);
  }

  return '<div class="alert alert-warning">Unknown route type</div>';
}

// Format a direct route
function formatDirectRoute(route) {
  // Format times
  const departureTime = formatTime(route.start_stop.time);
  const arrivalTime = formatTime(
    route.end_stop.predicted_time || route.end_stop.time
  );

  // Calculate travel time in minutes
  const travelMinutes = Math.round(route.travel_time);

  // Crowding badge
  let crowdingBadge = "";
  if (route.crowding) {
    const crowdingClass = `crowding-${route.crowding}`;
    crowdingBadge = `<span class="crowding ${crowdingClass}">${route.crowding}</span>`;
  }

  return `
      <div class="route-result">
        <div class="route-info">
          <div class="route-number">${route.route_id}</div>
          <div class="route-details">
            <h5>${route.route_name}</h5>
            <span class="route-time">${departureTime} → ${arrivalTime} (${travelMinutes} min)</span>
            ${crowdingBadge}
          </div>
        </div>
        <div class="route-path">
          <div class="stops">
            <div class="stop-point">
              <div class="stop-name">${route.start_stop.name}</div>
              <div class="stop-time">Depart: ${departureTime}</div>
            </div>
            <div class="stop-point">
              <div class="stop-name">${route.end_stop.name}</div>
              <div class="stop-time">Arrive: ${arrivalTime}</div>
            </div>
          </div>
        </div>
        <button class="btn btn-sm btn-primary mt-2" onclick="showRouteOnMap('${route.route_id}')">
          <i class="fas fa-map-marked-alt me-2"></i>Show on Map
        </button>
      </div>
    `;
}

// Format a transfer route
function formatTransferRoute(route) {
  // Format times
  const departureTime = formatTime(route.first_leg.start_stop.time);
  const transferArrivalTime = formatTime(route.first_leg.end_stop.time);
  const transferDepartureTime = formatTime(route.second_leg.start_stop.time);
  const arrivalTime = formatTime(route.second_leg.end_stop.time);

  // Calculate travel time in minutes
  const travelMinutes = Math.round(route.travel_time);

  // Calculate transfer wait time
  const transferWaitTime = calculateWaitTime(
    route.first_leg.end_stop.time,
    route.second_leg.start_stop.time
  );

  return `
      <div class="route-result">
        <div class="badge bg-warning text-dark position-absolute top-0 end-0 m-2">Transfer</div>
        <div class="route-info">
          <div class="route-number">${route.first_leg.route_id}</div>
          <div class="route-details">
            <h5>${route.first_leg.route_name}</h5>
            <span class="route-time">${departureTime} → ${transferArrivalTime}</span>
          </div>
        </div>
        <div class="route-path">
          <div class="stops">
            <div class="stop-point">
              <div class="stop-name">${route.first_leg.start_stop.name}</div>
              <div class="stop-time">Depart: ${departureTime}</div>
            </div>
            <div class="stop-point transfer-point">
              <div class="stop-name">${route.transfer_stop.name}</div>
              <div class="stop-time">Transfer: Wait ${transferWaitTime} min</div>
            </div>
          </div>
        </div>
        
        <div class="route-info mt-3">
          <div class="route-number">${route.second_leg.route_id}</div>
          <div class="route-details">
            <h5>${route.second_leg.route_name}</h5>
            <span class="route-time">${transferDepartureTime} → ${arrivalTime}</span>
          </div>
        </div>
        <div class="route-path">
          <div class="stops">
            <div class="stop-point">
              <div class="stop-name">${route.transfer_stop.name}</div>
              <div class="stop-time">Depart: ${transferDepartureTime}</div>
            </div>
            <div class="stop-point">
              <div class="stop-name">${route.second_leg.end_stop.name}</div>
              <div class="stop-time">Arrive: ${arrivalTime}</div>
            </div>
          </div>
        </div>
        
        <div class="d-flex mt-2">
          <span class="me-auto">Total travel time: ${travelMinutes} min</span>
          <button class="btn btn-sm btn-primary" onclick="showRouteOnMap('${route.first_leg.route_id}', '${route.second_leg.route_id}')">
            <i class="fas fa-map-marked-alt me-2"></i>Show on Map
          </button>
        </div>
      </div>
    `;
}

// Format time from "HH:MM:SS" to "HH:MM"
function formatTime(timeStr) {
  if (!timeStr) return "N/A";

  const parts = timeStr.split(":");
  if (parts.length >= 2) {
    let hours = parseInt(parts[0], 10);
    const minutes = parts[1];

    // Normalize hours if over 24 (for overnight routes)
    if (hours >= 24) {
      hours -= 24;
    }

    return `${hours.toString().padStart(2, "0")}:${minutes}`;
  }

  return timeStr;
}

// Calculate wait time between two times in minutes
function calculateWaitTime(arrivalTimeStr, departureTimeStr) {
  try {
    const arrParts = arrivalTimeStr.split(":");
    const depParts = departureTimeStr.split(":");

    let arrMinutes = parseInt(arrParts[0], 10) * 60 + parseInt(arrParts[1], 10);
    let depMinutes = parseInt(depParts[0], 10) * 60 + parseInt(depParts[1], 10);

    // Handle overnight routes
    if (depMinutes < arrMinutes && arrMinutes - depMinutes > 1000) {
      depMinutes += 1440; // Add 24 hours
    }

    return depMinutes - arrMinutes;
  } catch (e) {
    return "N/A";
  }
}

// Show route(s) on the map
function showRouteOnMap(routeId1, routeId2) {
  if (typeof displayRoute === "function") {
    // Clear previous routes
    if (typeof clearRouteDisplay === "function") {
      clearRouteDisplay();
    }

    // Display first route
    displayRoute(routeId1);

    // Display second route if it exists
    if (routeId2) {
      setTimeout(() => {
        displayRoute(routeId2);
      }, 1000);
    }
  } else {
    alert(
      "Map functionality not available. Please try again from the main page."
    );
  }
}

// Initialize search page
document.addEventListener("DOMContentLoaded", function () {
  // Initialize search form if it exists
  if (document.getElementById("route-search-form")) {
    initSearchForm();
  }

  // Initialize map clicks for search if map exists
  if (typeof initSearchMapClicks === "function" && typeof map !== "undefined") {
    initSearchMapClicks();
  }
});
