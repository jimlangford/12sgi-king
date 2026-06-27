/* po_timing.js — Hawaiian day/night phase engine
 * Anchored to Kula, Maui (lat 20.7749765, lon -156.310248, HST UTC-10, no DST).
 * Sets html[data-phase="po"|"la"] and injects a subtle badge with the next transition.
 *
 * Hawaiian reckoning: Pō (night) begins at SUNSET and belongs to the COMING day.
 * Lā (day) runs sunrise → sunset.
 *
 * Algorithm: NOAA solar position equations (same as sun_timing.py server-side).
 */
(function () {
  'use strict';

  var LAT = 20.7749765;
  var LON = -156.310248;   // negative = west
  var UTC_OFFSET = -10;    // HST, no DST ever

  function julianDayNumber(year, month, day) {
    var a = Math.floor((14 - month) / 12);
    var y = year + 4800 - a;
    var m = month + 12 * a - 3;
    return day + Math.floor((153 * m + 2) / 5) + 365 * y +
           Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
  }

  function sunEvents(jdn) {
    var n = jdn - 2451545 + 0.0008;
    var jStar = n - LON / 360.0;
    var M = ((357.5291 + 0.98560028 * jStar) % 360 + 360) % 360;
    var Mr = M * Math.PI / 180;
    var C = 1.9148 * Math.sin(Mr) + 0.02 * Math.sin(2 * Mr) + 0.0003 * Math.sin(3 * Mr);
    var lam = ((M + C + 180.0 + 102.9372) % 360 + 360) % 360;
    var lamR = lam * Math.PI / 180;
    var jTransit = 2451545 + jStar + 0.0053 * Math.sin(Mr) - 0.0069 * Math.sin(2 * lamR);
    var sinD = Math.sin(lamR) * Math.sin(23.4397 * Math.PI / 180);
    var cosD = Math.cos(Math.asin(sinD));
    var cosW = (Math.sin(-0.8333 * Math.PI / 180) - Math.sin(LAT * Math.PI / 180) * sinD) /
               (Math.cos(LAT * Math.PI / 180) * cosD);
    if (Math.abs(cosW) > 1) return null;
    var w0deg = Math.acos(cosW) * 180 / Math.PI;
    var toMs = function (jd) { return (jd - 2440587.5) * 86400 * 1000; };
    return {
      sunrise: toMs(jTransit - w0deg / 360),
      sunset:  toMs(jTransit + w0deg / 360)
    };
  }

  function getPhase() {
    var nowMs = Date.now();
    // Current date in HST
    var hst = new Date(nowMs + UTC_OFFSET * 3600000);
    var yr = hst.getUTCFullYear(), mo = hst.getUTCMonth() + 1, dy = hst.getUTCDate();
    var jdn = julianDayNumber(yr, mo, dy);
    var today = sunEvents(jdn);
    var tomorrow = sunEvents(jdn + 1);
    if (!today) return { phase: 'la', next: null, label: '' };

    var phase, next;
    if (nowMs >= today.sunset) {
      phase = 'po';
      next = tomorrow ? tomorrow.sunrise : null;
    } else if (nowMs < today.sunrise) {
      phase = 'po';
      next = today.sunrise;
    } else {
      phase = 'la';
      next = today.sunset;
    }

    var label = '';
    if (next) {
      var d = new Date(next + UTC_OFFSET * 3600000);
      var h = d.getUTCHours(), m = d.getUTCMinutes();
      var ampm = h >= 12 ? 'pm' : 'am';
      var h12 = h % 12 || 12;
      label = h12 + ':' + (m < 10 ? '0' : '') + m + ' ' + ampm;
    }
    return { phase: phase, next: next, label: label };
  }

  function fmtBadge(info) {
    if (info.phase === 'po') {
      return 'Pō' + (info.label ? ' · Lā ' + info.label : '');
    }
    return 'Lā' + (info.label ? ' · Pō ' + info.label : '');
  }

  var _badge = null;
  var _styleEl = null;
  var _timer = null;

  function injectStyle() {
    if (_styleEl) return;
    _styleEl = document.createElement('style');
    _styleEl.textContent = [
      /* Po: override the ambient glow to cool indigo instead of gold */
      'html[data-phase="po"] { --glow-gold: radial-gradient(1200px 620px at 16% -10%, rgba(80,60,160,0.10), transparent 60%); }',
      'html[data-phase="po"] { --glow-blue: radial-gradient(900px 520px at 102% -4%, rgba(60,80,180,0.08), transparent 55%); }',
      /* Badge */
      '#po-la-badge {',
      '  position: fixed; bottom: 14px; left: 14px; z-index: 9999;',
      '  font-family: "JetBrains Mono", monospace; font-size: 10.5px;',
      '  padding: 3px 10px; border-radius: 20px;',
      '  border: 1px solid #34301f; background: #16140f;',
      '  color: #756b56; letter-spacing: 0.5px;',
      '  pointer-events: none; user-select: none;',
      '  transition: color 1.2s, border-color 1.2s;',
      '}',
      '#po-la-badge[data-phase="po"] {',
      '  color: #9090d8; border-color: #3a3560;',
      '}',
      '#po-la-badge[data-phase="la"] {',
      '  color: #b3a98f; border-color: #34301f;',
      '}'
    ].join('\n');
    document.head.appendChild(_styleEl);
  }

  function injectBadge() {
    if (_badge) return;
    _badge = document.createElement('div');
    _badge.id = 'po-la-badge';
    document.body.appendChild(_badge);
  }

  function applyPhase() {
    if (_timer) clearTimeout(_timer);
    var info = getPhase();

    document.documentElement.dataset.phase = info.phase;

    if (_badge) {
      _badge.textContent = fmtBadge(info);
      _badge.dataset.phase = info.phase;
    }

    // Schedule next update: fire 5s after the next transition, or check again in 60s
    var delay = 60000;
    if (info.next) {
      var ms = info.next - Date.now();
      if (ms > 0 && ms < 86400000) {
        delay = ms + 5000;
      }
    }
    _timer = setTimeout(applyPhase, delay);
  }

  // Set data-phase immediately (before body paint) for CSS pre-computation
  (function () {
    try {
      var info = getPhase();
      document.documentElement.dataset.phase = info.phase;
    } catch (e) {}
  })();

  // Inject badge + full CSS after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      injectStyle();
      injectBadge();
      applyPhase();
    });
  } else {
    injectStyle();
    injectBadge();
    applyPhase();
  }
})();
