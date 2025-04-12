// Realtime transit data handling for Calgary Transit App

// Store current vehicle and trip data
let currentVehicles = [];
let currentTrips = [];

// Initialize realtime updates
function initRealtimeUpdates() {
  // Initial data load
  loadVehicleData();
  loadTripUpdates();

  // Setup refresh intervals
  setInterval(loadVehicleData, 30000); // Refresh vehicles every 30 seconds
  setInterval(loadTripUpdates, 60000); // Refresh trip updates every 60 seconds
}

// Load real-time vehicle position data
function loadVehicleData() {
  fetch("/api/vehicles")
    .then((response) => response.json())
    .then((data) => {
      currentVehicles = data;

      // Update vehicle count display
      updateVehicleCount();

      // If map is initialized, update vehicle markers
      if (typeof loadVehiclePositions === "function") {
        loadVehiclePositions();
      }

      // Update any active vehicle tracking
      if (typeof updateTrackedVehicle === "function") {
        updateTrackedVehicle();
      }

      // Dispatch custom event that vehicle data has been updated
      document.dispatchEvent(
        new CustomEvent("vehicles-updated", { detail: currentVehicles })
      );
    })
    .catch((error) => {
      console.error("Error loading vehicle data:", error);
    });
}

// Load real-time trip updates (delays, etc.)
function loadTripUpdates() {
  fetch("/api/trips")
    .then((response) => response.json())
    .then((data) => {
      currentTrips = data;

      // Update any displayed trip predictions
      updatePredictions();

      // Dispatch custom event that trip data has been updated
      document.dispatchEvent(
        new CustomEvent("trips-updated", { detail: currentTrips })
      );
    })
    .catch((error) => {
      console.error("Error loading trip updates:", error);
    });
}

// Update vehicle count display
function updateVehicleCount() {
  const countElement = document.getElementById("vehicle-count");
  if (countElement) {
    countElement.textContent = currentVehicles.length;
  }
}

// Update predictions for stops
function updatePredictions() {
  // Find all elements with prediction data
  const predictionElements = document.querySelectorAll(
    "[data-trip-id][data-stop-id]"
  );

  predictionElements.forEach((element) => {
    const tripId = element.getAttribute("data-trip-id");
    const stopId = element.getAttribute("data-stop-id");

    // Find matching trip update
    const tripUpdate = currentTrips.find((trip) => trip.trip_id === tripId);
    if (tripUpdate) {
      const stopUpdate = (tripUpdate.stop_time_updates || []).find(
        (update) => update.stop_id === stopId
      );

      if (stopUpdate) {
        // Determine delay in minutes
        let delayMinutes = 0;
        if (stopUpdate.arrival_delay) {
          delayMinutes = Math.round(stopUpdate.arrival_delay / 60);
        } else if (stopUpdate.departure_delay) {
          delayMinutes = Math.round(stopUpdate.departure_delay / 60);
        }

        // Update the display
        let statusText = "";
        let statusClass = "";

        if (delayMinutes > 5) {
          statusText = `Delayed by ${delayMinutes} min`;
          statusClass = "text-warning";
        } else if (delayMinutes < -2) {
          statusText = `${Math.abs(delayMinutes)} min early`;
          statusClass = "text-info";
        } else {
          statusText = "On time";
          statusClass = "text-success";
        }

        // Update element
        element.textContent = statusText;
        element.className = statusClass;
      }
    }
  });

  // Get more detailed predictions
  fetchDetailedPredictions();
}

// Fetch detailed predictions from the ML model
function fetchDetailedPredictions() {
  const detailedPredictionElements = document.querySelectorAll(
    "[data-prediction-trip-id][data-prediction-stop-id]"
  );

  detailedPredictionElements.forEach((element) => {
    const tripId = element.getAttribute("data-prediction-trip-id");
    const stopId = element.getAttribute("data-prediction-stop-id");

    fetch(`/api/predictions/${tripId}/${stopId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          console.error(
            `Error getting prediction for ${tripId}/${stopId}:`,
            data.error
          );
          return;
        }

        // Update time display
        const timeElement = element.querySelector(".predicted-time");
        if (timeElement && data.predicted_time) {
          // Format the time (HH:MM)
          const timeParts = data.predicted_time.split(":");
          const formattedTime = `${timeParts[0]}:${timeParts[1]}`;
          timeElement.textContent = formattedTime;
        }

        // Update crowding display
        const crowdingElement = element.querySelector(".predicted-crowding");
        if (crowdingElement && data.crowding) {
          crowdingElement.textContent =
            data.crowding.charAt(0).toUpperCase() + data.crowding.slice(1);

          // Add appropriate class
          crowdingElement.className = "predicted-crowding crowding";
          crowdingElement.classList.add(`crowding-${data.crowding}`);
        }
      })
      .catch((error) => {
        console.error(
          `Error fetching prediction for ${tripId}/${stopId}:`,
          error
        );
      });
  });
}

// Track a specific vehicle
function trackVehicle(vehicleId) {
  // Store the tracked vehicle ID
  localStorage.setItem("trackedVehicle", vehicleId);

  // Update immediately
  updateTrackedVehicle();
}

// Update the tracked vehicle display
function updateTrackedVehicle() {
  const vehicleId = localStorage.getItem("trackedVehicle");
  if (!vehicleId) return;

  const trackedElement = document.getElementById("tracked-vehicle");
  if (!trackedElement) return;

  // Find vehicle data
  const vehicle = currentVehicles.find((v) => v.id === vehicleId);

  if (vehicle) {
    // Format timestamp
    const timestamp = vehicle.timestamp
      ? new Date(vehicle.timestamp * 1000).toLocaleTimeString()
      : "Unknown";

    // Update display
    trackedElement.innerHTML = `
      <div class="card bg-dark text-light">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h5 class="mb-0">Tracking Vehicle ${vehicleId}</h5>
          <button class="btn btn-sm btn-danger" onclick="stopTracking()">Stop Tracking</button>
        </div>
        <div class="card-body">
          <p><strong>Route:</strong> ${vehicle.route_id || "Unknown"}</p>
          <p><strong>Status:</strong> ${getStatusText(
            vehicle.current_status
          )}</p>
          <p><strong>Last Updated:</strong> ${timestamp}</p>
          <p><strong>Location:</strong> ${vehicle.latitude?.toFixed(
            6
          )}, ${vehicle.longitude?.toFixed(6)}</p>
          <button class="btn btn-primary" onclick="centerMapOnVehicle('${vehicleId}')">
            <i class="fas fa-crosshairs me-2"></i>Center on Map
          </button>
        </div>
      </div>
    `;
    trackedElement.style.display = "block";
  } else {
    trackedElement.innerHTML = `
      <div class="alert alert-warning">
        Vehicle ${vehicleId} is not currently active or reporting. 
        <button class="btn btn-sm btn-secondary ms-2" onclick="stopTracking()">Stop Tracking</button>
      </div>
    `;
    trackedElement.style.display = "block";
  }
}

// Stop tracking a vehicle
function stopTracking() {
  localStorage.removeItem("trackedVehicle");

  const trackedElement = document.getElementById("tracked-vehicle");
  if (trackedElement) {
    trackedElement.style.display = "none";
  }
}

// Center map on a tracked vehicle
function centerMapOnVehicle(vehicleId) {
  // Find vehicle data
  const vehicle = currentVehicles.find((v) => v.id === vehicleId);

  if (
    vehicle &&
    vehicle.latitude &&
    vehicle.longitude &&
    typeof map !== "undefined"
  ) {
    map.setView([vehicle.latitude, vehicle.longitude], 17);

    // Flash the marker
    const marker = vehicleMarkers.find((m) => {
      return (
        m.getLatLng().lat === vehicle.latitude &&
        m.getLatLng().lng === vehicle.longitude
      );
    });

    if (marker) {
      marker.openPopup();

      // Add a temporary highlight
      const highlight = L.circle([vehicle.latitude, vehicle.longitude], {
        color: "#fff",
        fillColor: "#17a2b8",
        fillOpacity: 0.3,
        radius: 50,
      }).addTo(map);

      // Remove after animation
      setTimeout(() => {
        map.removeLayer(highlight);
      }, 3000);
    }
  }
}

// Initialize when document is ready
document.addEventListener("DOMContentLoaded", function () {
  // Initialize realtime updates
  initRealtimeUpdates();

  // Check for tracked vehicle
  if (localStorage.getItem("trackedVehicle")) {
    updateTrackedVehicle();
  }
});
