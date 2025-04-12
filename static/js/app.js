/**
 * Main JavaScript for the Transit App
 */

// Global variables
let globalMap = null;
let userLocationMarker = null;
let userLocation = null;

// Initialize common functionality when document is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize Bootstrap tooltips
  if (typeof bootstrap !== "undefined") {
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach((tooltip) => new bootstrap.Tooltip(tooltip));
  }

  // Set up search form for geocoding
  setupGeocoding();
});

/**
 * Set up geocoding functionality for address inputs
 */
function setupGeocoding() {
  const startLocationInput = document.getElementById("start-location");
  const endLocationInput = document.getElementById("end-location");

  if (startLocationInput) {
    startLocationInput.addEventListener("blur", function () {
      if (this.value && this.value !== "Current Location") {
        geocodeAddress(this.value, function (lat, lon) {
          document.getElementById("start-lat").value = lat;
          document.getElementById("start-lon").value = lon;
        });
      }
    });
  }

  if (endLocationInput) {
    endLocationInput.addEventListener("blur", function () {
      if (this.value) {
        geocodeAddress(this.value, function (lat, lon) {
          document.getElementById("end-lat").value = lat;
          document.getElementById("end-lon").value = lon;
        });
      }
    });
  }
}

/**
 * Geocode an address to get coordinates
 *
 * @param {string} address The address to geocode
 * @param {function} callback Function to call with results (lat, lon)
 */
function geocodeAddress(address, callback) {
  // Using Nominatim for geocoding (in production, use commercial service)
  fetch(
    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
      address
    )}&limit=1`
  )
    .then((response) => response.json())
    .then((data) => {
      if (data && data.length > 0) {
        const lat = parseFloat(data[0].lat);
        const lon = parseFloat(data[0].lon);
        callback(lat, lon);
      } else {
        showToast(
          "Address not found. Please try a different address.",
          "warning"
        );
      }
    })
    .catch((error) => {
      console.error("Geocoding error:", error);
      showToast("Error geocoding address. Please try again.", "danger");
    });
}

/**
 * Get the user's current location using the Geolocation API
 *
 * @param {function} successCallback Function to call on successful location (position)
 * @param {function} errorCallback Function to call on error (error)
 */
function getUserLocation(successCallback, errorCallback) {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      function (position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        userLocation = { lat, lon };

        if (successCallback) {
          successCallback(position);
        }
      },
      function (error) {
        console.error("Error getting location:", error);

        if (errorCallback) {
          errorCallback(error);
        } else {
          let errorMessage = "Unable to get your location.";
          switch (error.code) {
            case error.PERMISSION_DENIED:
              errorMessage +=
                " Please allow location access in your browser settings.";
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage += " Location information is unavailable.";
              break;
            case error.TIMEOUT:
              errorMessage += " The request timed out.";
              break;
          }
          showToast(errorMessage, "warning");
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 0,
      }
    );
  } else {
    showToast("Geolocation is not supported by your browser.", "warning");
    if (errorCallback) {
      errorCallback({ code: 0, message: "Geolocation not supported" });
    }
  }
}

/**
 * Show a toast notification
 *
 * @param {string} message The message to display
 * @param {string} type The type of toast (success, danger, warning, info)
 */
function showToast(message, type = "info") {
  // Check if toast container exists, create if not
  let toastContainer = document.querySelector(".toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.className =
      "toast-container position-fixed bottom-0 end-0 p-3";
    document.body.appendChild(toastContainer);
  }

  // Create toast element
  const toastId = "toast-" + Date.now();
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-white bg-${type} border-0`;
  toast.setAttribute("role", "alert");
  toast.setAttribute("aria-live", "assertive");
  toast.setAttribute("aria-atomic", "true");
  toast.setAttribute("id", toastId);

  toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

  toastContainer.appendChild(toast);

  // Initialize and show the toast
  if (typeof bootstrap !== "undefined") {
    const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 5000 });
    bsToast.show();

    // Remove from DOM after hidden
    toast.addEventListener("hidden.bs.toast", function () {
      this.remove();
    });
  } else {
    // Fallback if Bootstrap JS is not available
    toast.style.display = "block";
    setTimeout(() => {
      toast.remove();
    }, 5000);
  }
}

/**
 * Format a date to HH:MM format
 *
 * @param {Date} date The date to format
 * @return {string} Formatted time string
 */
function formatTime(date) {
  if (!(date instanceof Date)) {
    return "--:--";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/**
 * Calculate distance between two coordinates in kilometers (Haversine formula)
 *
 * @param {number} lat1 Starting latitude
 * @param {number} lon1 Starting longitude
 * @param {number} lat2 Ending latitude
 * @param {number} lon2 Ending longitude
 * @return {number} Distance in kilometers
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Fetch data from API with error handling
 *
 * @param {string} url The API URL to fetch
 * @param {Object} options Fetch options
 * @return {Promise} Promise resolving to the data
 */
async function fetchAPI(url, options = {}) {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("API fetch error:", error);
    showToast("Error fetching data. Please try again.", "danger");
    throw error;
  }
}

/**
 * Create a custom icon for map markers
 *
 * @param {string} type The type of marker (user, stop, vehicle, etc.)
 * @param {string} iconHtml Optional HTML for the icon content
 * @return {L.DivIcon} Leaflet div icon
 */
function createCustomIcon(type, iconHtml = null) {
  let className, html, size;

  switch (type) {
    case "user":
      className = "user-location-marker";
      html = iconHtml || '<i class="fas fa-user"></i>';
      size = [24, 24];
      break;
    case "stop":
      className = "bus-stop-marker";
      html = iconHtml || '<i class="fas fa-bus"></i>';
      size = [20, 20];
      break;
    case "vehicle":
      className = "vehicle-marker";
      html = iconHtml || '<i class="fas fa-bus"></i>';
      size = [22, 22];
      break;
    case "start":
      className = "start-location-marker";
      html = iconHtml || '<i class="fas fa-play-circle"></i>';
      size = [24, 24];
      break;
    case "end":
      className = "end-location-marker";
      html = iconHtml || '<i class="fas fa-flag-checkered"></i>';
      size = [24, 24];
      break;
    default:
      className = "default-marker";
      html = iconHtml || '<i class="fas fa-map-marker-alt"></i>';
      size = [20, 20];
  }

  return L.divIcon({
    className: className,
    html: html,
    iconSize: size,
  });
}
