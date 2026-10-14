// Naver Map sidebar panel (placeholder: renders HA's <ha-map> only).
class NaverMapPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this._map) this._map.hass = hass;
  }

  connectedCallback() {
    if (this._map) return;
    console.info("[naver-map-panel] ha-map defined:", !!customElements.get("ha-map"));
    this.style.display = "block";
    this.style.height = "100%";
    this._map = document.createElement("ha-map");
    this._map.style.height = "100%";
    this._map.hass = this._hass;
    this.appendChild(this._map);
  }
}

customElements.define("naver-map-panel", NaverMapPanel);
