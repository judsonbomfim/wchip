/*
{
  name: 'Inspinia',
  title: 'INSPINIA - Responsive Bootstrap 5 Admin Dashboard Template',
  description: 'Inspinia is the #1 best-selling admin dashboard template on Wrapmarket. Perfect for building CRM, CMS, project management tools, and custom web apps with clean UI, responsive design, and powerful features.',
  author: 'WebAppLayers',
  version: '5.0.0'
}
*/

// App
class App {
  // Portlet Widget (Card Reload, Collapse, and Delete)
  initPortletCard() {

    // Handle card close
    document.querySelectorAll('[data-action="card-close"]').forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault()
        const card = btn.closest(".card")
        if (card) {
          card.style.transition = "opacity 0.3s ease"
          card.style.opacity = "0"
          setTimeout(() => card.remove(), 300)
        }
      })
    })

    // Handle card toggle
    document.querySelectorAll('[data-action="card-toggle"]').forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault()

        const card = btn.closest(".card")
        const cardBody = card.querySelector(".card-body")

        if (card && cardBody) {
          cardBody.style.transition = "height 0.35s ease-in-out, margin 0.35s ease-in-out"

          if (card.classList.contains("card-collapsed")) {
            card.classList.remove("card-collapsed")

            cardBody.style.height = cardBody.scrollHeight + "px"
            cardBody.style.overflow = "hidden"

            cardBody.addEventListener(
              "transitionend",
              () => {
                cardBody.style.height = "auto"
                cardBody.style.overflow = "visible"
              },
              { once: true }
            )
          } else {
            cardBody.style.height = cardBody.scrollHeight + "px"
            cardBody.style.overflow = "hidden"
            cardBody.offsetHeight
            cardBody.style.height = "0"
            card.classList.add("card-collapsed")
          }
        }
      })
    })

    // Handle card refresh
    document.querySelectorAll('[data-action="card-refresh"]').forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault()

        const card = button.closest(".card")
        let overlay = card.querySelector(".card-overlay")

        if (!overlay) {
          overlay = document.createElement("div")
          overlay.className = "card-overlay"

          const spinner = document.createElement("div")
          spinner.className = "size-8 animate-spin rounded-full border-3 border-primary border-t-transparent rounded-[999px] text-primary"

          overlay.appendChild(spinner)
          card.appendChild(overlay)
        }

        overlay.style.display = "flex"

        setTimeout(() => {
          overlay.style.display = "none"
        }, 1500)
      })
    })

    // Handle code preview collapse
    document.querySelectorAll('[data-action="code-collapse"]').forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault()
        const card = btn.closest(".card")
        const codeBody = card.querySelector(".code-body")

        if (card && codeBody) {
          codeBody.style.transition = "height 0.35s ease-in-out"

          const isHidden = window.getComputedStyle(codeBody).display === "none"

          if (isHidden) {
            codeBody.style.display = "block"
            codeBody.style.height = "0"
            codeBody.style.overflow = "hidden"

            const fullHeight = codeBody.scrollHeight

            codeBody.offsetHeight
            codeBody.style.height = fullHeight + "px"

            codeBody.addEventListener(
              "transitionend",
              () => {
                codeBody.style.height = "auto"
                codeBody.style.overflow = "visible"
              },
              { once: true }
            )
          } else {
            codeBody.style.height = codeBody.scrollHeight + "px"
            codeBody.style.overflow = "hidden"
            codeBody.offsetHeight
            codeBody.style.height = "0"

            codeBody.addEventListener(
              "transitionend",
              () => {
                codeBody.style.display = "none"
                codeBody.style.height = null
              },
              { once: true }
            )
          }
        }
      })
    })

  }

  initSidenav() {
    var self = this
    var pageUrl = window.location.href.split(/[?#]/)[0]
    document.querySelectorAll("ul.side-nav .menu-item > a").forEach((element) => {
      if (element.href === pageUrl) {
        // Add active to the clicked link
        element.classList.add("active")
        // Add active to its parent .menu-item
        let parentLi = element.closest(".menu-item")
        if (parentLi) {
          parentLi.classList.add("active")
        }
        let parentAccordion = element.closest(".hs-accordion")
        while (parentAccordion) {
          parentAccordion.classList.add("active")
          const toggle = parentAccordion.querySelector(":scope > .hs-accordion-toggle")
          if (toggle) {
            toggle.classList.add("active")
            toggle.setAttribute("aria-expanded", "true")
          }
          const submenu = parentAccordion.querySelector(":scope > .hs-accordion-content")
          if (submenu) {
            submenu.classList.remove("hidden")
          }
          parentAccordion = parentAccordion.parentElement?.closest(".hs-accordion")
        }
      }
    })

    setTimeout(function () {
      var activatedItem = document.querySelector("ul.side-nav .menu-item.active a.active")
      const scrollContainer = document.querySelector("#app-menu .simplebar-content-wrapper")

      if (activatedItem && scrollContainer) {
        var simplebarContent = document.querySelector("#app-menu .simplebar-content-wrapper")
        var offset = activatedItem.offsetTop - 265
        if (simplebarContent && offset > 100) {
          scrollTo(simplebarContent, offset, 600)
        }
      }
    }, 200)

    // scrollTo (Sidenav Active Menu)
    function easeInOutQuad(t, b, c, d) {
      t /= d / 2
      if (t < 1) return (c / 2) * t * t + b
      t--
      return (-c / 2) * (t * (t - 2) - 1) + b
    }
    function scrollTo(element, to, duration) {
      var start = element.scrollTop,
        change = to - start,
        currentTime = 0,
        increment = 20
      var animateScroll = function () {
        currentTime += increment
        var val = easeInOutQuad(currentTime, start, change, duration)
        element.scrollTop = val
        if (currentTime < duration) {
          setTimeout(animateScroll, increment)
        }
      }
      animateScroll()
    }
  }

  reverseQuery(element, query) {
    while (element) {
      if (element.parentElement) {
        if (element.parentElement.querySelector(query) === element) return element
      }
      element = element.parentElement
    }
    return null
  }

  initFullScreen() {
    // helper functions
    function getFsElement() {
      return document.fullscreenElement || document.webkitFullscreenElement
    }

    function enterFullscreen(el) {
      if (el.requestFullscreen) {
        return el.requestFullscreen()
      } else if (el.webkitRequestFullscreen) {
        // Safari
        return el.webkitRequestFullscreen()
      }
    }

    function exitFullscreen() {
      if (document.exitFullscreen) {
        return document.exitFullscreen()
      } else if (document.webkitExitFullscreen) {
        // Safari
        return document.webkitExitFullscreen()
      }
    }

    function toggleFullscreen(el) {
      if (getFsElement()) {
        exitFullscreen()
      } else {
        enterFullscreen(el)
      }
    }

    // attach click handler to any element with data-toggle="fullscreen"
    document.addEventListener("click", function (e) {
      const trigger = e.target.closest('[data-toggle="fullscreen"]')
      const btn = document.querySelector("[data-toggle='fullscreen']")

      if (trigger) {
        e.preventDefault()
        btn.classList.toggle("fullscreen-active")
        toggleFullscreen(document.documentElement)
      }
    })
  }

  // Counter for Numbers
  initCounter() {
    const counters = document.querySelectorAll("[data-target]")

    const observer = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const counter = entry.target

            // Parse the target value, removing any commas first
            let target = counter.getAttribute("data-target").replace(/,/g, "")

            target = parseFloat(target) // Convert to float

            let current = 0 // Initial counter value

            let increment // Increment step for smooth animation

            if (Number.isInteger(target)) {
              increment = Math.max(1, Math.floor(target / 25)) // Increment for integer values
            } else {
              increment = target / 25 // Increment for float values
            }

            const updateCounter = () => {
              if (current < target) {
                current += increment
                if (current > target) current = target // Avoid overshooting
                // Format as integer or decimal and add commas
                counter.innerText = formatNumber(current)
                requestAnimationFrame(updateCounter) // Continue animation frame by frame
              } else {
                counter.innerText = formatNumber(target) // Final display
              }
            }

            updateCounter() // Start the animation

            // Function to format numbers with commas and decimal places if necessary
            function formatNumber(num) {
              if (num % 1 === 0) {
                // Format as integer with commas
                return num.toLocaleString()
              } else {
                // Format as float with two decimal places and commas
                return num.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })
              }
            }

            observer.unobserve(counter)
          }
        })
      },
      {
        threshold: 1, // Adjust this threshold to control when to trigger (e.g., 0.5 means 50% of the element is visible)
      }
    )

    counters.forEach((counter) => observer.observe(counter))
  }

  // Code Preview
  initCodePreview() {
    if (typeof Prism !== "undefined" && Prism.plugins && Prism.plugins.NormalizeWhitespace) {
      Prism.plugins.NormalizeWhitespace.setDefaults({
        "remove-trailing": true,
        "remove-indent": true,
        "left-trim": true,
        "right-trim": true,
        "tabs-to-spaces": 4,
        "spaces-to-tabs": 4,
      })
    }
  }

  init() {
    this.initSidenav()
    this.initFullScreen()
    this.initPortletCard()
    this.initCounter()
    this.initCodePreview()
  }
}

// Layout Customizer
class LayoutCustomizer {
  constructor() {
    this.html = document.documentElement
    this.config = {}
  }

  init() {
    this.initConfig()
    this.monochromeMode()
    this.initSwitchListener()
    this.initWindowSize()
    this._adjustLayout()
    this.setSwitchFromConfig()
    this.activeThemeDropdownItem()

    this.openCustomizer() // only for demo (not required)
  }

  // only for demo (not required)
  isFirstVisit() {
    const visited = localStorage.getItem("__user_has_visited__")
    if (!visited) {
      localStorage.setItem("__user_has_visited__", "true")
      return true
    }
    return false
  }

  // only for demo (not required)
  openCustomizer() {
    const layoutCustomizer = document.getElementById("theme-settings-offcanvas")
    if (layoutCustomizer && this.isFirstVisit()) {
      const offcanvas = new bootstrap.Offcanvas(layoutCustomizer)
      setTimeout(() => {
        offcanvas.show()
      }, 1000)
    }
  }

  initConfig() {
    this.defaultConfig = JSON.parse(JSON.stringify(window.defaultConfig))
    this.config = JSON.parse(JSON.stringify(window.config))
    this.setSwitchFromConfig()
  }

  monochromeMode() {
    const toggleBtn = document.getElementById("monochrome-mode")
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        this.config.monochrome = !this.config.monochrome

        if (this.config.monochrome) {
          this.html.classList.add("monochrome")
        } else {
          this.html.classList.remove("monochrome")
        }

        this.setSwitchFromConfig()
      })
    }
  }

  changeSkin(skin) {
    this.config["skin"] = skin
    this.html.setAttribute("data-skin", skin)
    this.setSwitchFromConfig()
  }

  changeMenuColor(color) {
    this.config["sidenav-color"] = color
    this.html.setAttribute("data-menu-color", color)
    this.setSwitchFromConfig()
  }

  changeSidenavSize(size, save = true) {
    this.html.setAttribute("data-sidenav-size", size)
    if (save) {
      this.config["sidenav-size"] = size
      this.setSwitchFromConfig()
    }
  }

  changeLayoutPosition(position) {
    this.config["position"] = position
    this.html.setAttribute("data-layout-position", position)
    this.setSwitchFromConfig()
  }

  changeTheme(color) {
    this.config["theme"] = color
    this.html.setAttribute("data-theme", color === "system" ? this.getSystemTheme() : color)
    this.setSwitchFromConfig()
    this.activeThemeDropdownItem()
  }

  changeTopbarColor(color) {
    this.config["topbar-color"] = color
    this.html.setAttribute("data-topbar-color", color)
    this.setSwitchFromConfig()
  }

  changeLayoutWidth(width) {
    this.config.width = width
    this.html.setAttribute("data-layout-width", width)
    this.setSwitchFromConfig()
  }

  changeLayoutDirection(dir) {
    this.config.dir = dir
    this.html.setAttribute("dir", dir)
    this.setSwitchFromConfig()
  }

  changeSidebarUser(showUser) {
    this.config["sidenav-user"] = showUser
    if (showUser) {
      this.html.setAttribute("data-sidenav-user", showUser)
    } else {
      this.html.removeAttribute("data-sidenav-user")
    }
    this.setSwitchFromConfig()
  }

  resetTheme() {
    this.config = JSON.parse(JSON.stringify(window.defaultConfig))
    this.changeSkin(this.config["skin"])
    this.changeMenuColor(this.config["sidenav-color"])
    this.changeSidenavSize(this.config["sidenav-size"])
    this.changeTheme(this.config["theme"])
    this.changeLayoutPosition(this.config["position"])
    this.changeTopbarColor(this.config["topbar-color"])
    this.changeLayoutWidth(this.config["width"])
    this.changeLayoutDirection(this.config["dir"])
    this.changeSidebarUser(this.config["sidenav-user"])
    this._adjustLayout()
  }

  getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  }

  setSwitchFromConfig() {
    const config = this.config

    sessionStorage.setItem("__THEME_CONFIG__", JSON.stringify(config))

    document.querySelectorAll("#theme-customization input[type=radio]").forEach((cb) => (cb.checked = false))

    const select = (name, val) => document.querySelector(`input[name="${name}"][value="${val}"]`)
    const toggle = (sel, state) => {
      const el = document.querySelector(sel)
      if (el) el.checked = state
    }

    toggle('input[name="sidebar-user"]', config["sidenav-user"] === true)
    ;[
      ["data-skin", config.skin],
      ["data-theme", config.theme],
      ["data-topbar-color", config["topbar-color"]],
      ["data-menu-color", config["sidenav-color"]],
      ["data-sidenav-size", config["sidenav-size"]],
      ["data-layout-position", config["position"]],
      ["data-layout-width", config["width"]],
      ["dir", config["dir"]],
    ].forEach(([name, val]) => {
      const el = select(name, val)
      if (el) el.checked = true
    })
  }

  initSwitchListener() {
    const bindChange = (selector, handler) => {
      document.querySelectorAll(selector).forEach((input) => input.addEventListener("change", () => handler(input)))
    }

    // Bind theme and layout related radios
    bindChange('input[name="data-skin"]', (input) => this.changeSkin(input.value))
    bindChange('input[name="data-theme"]', (input) => this.changeTheme(input.value))
    bindChange('input[name="data-topbar-color"]', (input) => this.changeTopbarColor(input.value))
    bindChange('input[name="data-menu-color"]', (input) => this.changeMenuColor(input.value))
    bindChange('input[name="data-sidenav-size"]', (input) => this.changeSidenavSize(input.value))
    bindChange('input[name="data-layout-position"]', (input) => this.changeLayoutPosition(input.value))
    bindChange('input[name="data-layout-width"]', (input) => this.changeLayoutWidth(input.value))
    bindChange('input[name="dir"]', (input) => this.changeLayoutDirection(input.value))
    bindChange('input[name="sidebar-user"]', (input) => this.changeSidebarUser(input.checked))

    const themeToggle = document.getElementById("light-dark-mode")
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const newTheme = this.config["theme"] === "light" ? "dark" : "light"
        this.changeTheme(newTheme)
      })
    }

    const resetBtn = document.querySelector("#reset-layout")
    if (resetBtn) {
      resetBtn.addEventListener("click", () => this.resetTheme())
    }

    const toggleBtn = document.querySelector(".sidenav-toggle-button")
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => this._toggleSidebar())
    }

    const closeBtn = document.querySelector(".button-close-offcanvas")
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        this.html.classList.remove("sidebar-enable")
        this.hideBackdrop()
      })
    }

    document.querySelectorAll(".button-on-hover").forEach((el) => {
      el.addEventListener("click", () => {
        const current = this.html.getAttribute("data-sidenav-size")
        this.changeSidenavSize(current === "on-hover-active" ? "on-hover" : "on-hover-active", true)
      })
    })

    document.querySelectorAll("#button-hover-toggle").forEach((el) => {
      el.addEventListener("click", () => {
        const current = this.html.getAttribute("data-sidenav-size")
        this.changeSidenavSize(current === "on-hover-active" ? "on-hover" : "on-hover-active", true)
      })
    })
  }

  _toggleSidebar() {
    const current = this.html.getAttribute("data-sidenav-size")
    const isOffcanvas = current === "offcanvas"
    const configSize = this.config["sidenav-size"]

    if (isOffcanvas) {
      this.showBackdrop()
    } else if (configSize === "compact") {
      this.changeSidenavSize(current === "condensed" ? "compact" : "condensed", false)
    } else {
      this.changeSidenavSize(current === "condensed" ? "default" : "condensed", true)
    }

    this.html.classList.toggle("sidenav-enable")
  }

  showBackdrop() {
    const backdrop = document.createElement("div")
    backdrop.id = "custom-backdrop"
    backdrop.className = "transition duration fixed inset-0 bg-default-900/50 z-40"
    document.body.appendChild(backdrop)
    backdrop.addEventListener("click", () => {
      this.html.classList.remove("sidenav-enable")
      this.hideBackdrop()
    })
  }

  hideBackdrop() {
    const backdrop = document.getElementById("custom-backdrop")
    if (backdrop) {
      document.body.removeChild(backdrop)
    }
  }

  _adjustLayout() {
    const width = window.innerWidth
    const size = this.config["sidenav-size"]

    if (width <= 767.98) {
      this.changeSidenavSize("offcanvas", false)
    } else if (width <= 1140 && !["offcanvas"].includes(size)) {
      this.changeSidenavSize(size === "on-hover" ? "condensed" : "condensed", false)
    } else {
      this.changeSidenavSize(size)
    }
  }

  initWindowSize() {
    window.addEventListener("resize", () => this._adjustLayout())
  }

  activeThemeDropdownItem() {
    const inputs = document.querySelectorAll('.theme-mode [name="data-theme"]')
    const theme = this.config["theme"]

    if (inputs && inputs.length > 0) {
      inputs.forEach((input) => {
        const isSelected = input.value === theme
        input.parentElement.classList.toggle("active", isSelected)

        if (isSelected) {
          const lightIcon = document.getElementById("theme-icon-light")
          const darkIcon = document.getElementById("theme-icon-dark")
          const systemIcon = document.getElementById("theme-icon-system")

          if (lightIcon) lightIcon.classList.toggle("hidden", theme !== "light")
          if (darkIcon) darkIcon.classList.toggle("hidden", theme !== "dark")
          if (systemIcon) systemIcon.classList.toggle("hidden", theme !== "system")
        }
      })
    }
  }
}

class Plugins {
    init() {
        // comment or remove plugins you don't need
        this.initFlatPicker()
        this.initTouchSpin()
    }

    // Flatpickr / Timepickr
    initFlatPicker() {
        document.querySelectorAll("[data-provider]").forEach((item) => {
            const type = item.getAttribute("data-provider")
            const attrs = item.attributes
            const dateConfig = { disableMobile: true, defaultDate: new Date() }

            if (type === "flatpickr") {
                if (attrs["data-date-format"]) dateConfig.dateFormat = attrs["data-date-format"].value
                if (attrs["data-enable-time"]) {
                    dateConfig.enableTime = true
                    dateConfig.dateFormat += " H:i"
                }
                if (attrs["data-altFormat"]) {
                    dateConfig.altInput = true
                    dateConfig.altFormat = attrs["data-altFormat"].value
                }
                if (attrs["data-minDate"]) dateConfig.minDate = attrs["data-minDate"].value
                if (attrs["data-maxDate"]) dateConfig.maxDate = attrs["data-maxDate"].value
                if (attrs["data-default-date"]) dateConfig.defaultDate = attrs["data-default-date"].value
                if (attrs["data-multiple-date"]) dateConfig.mode = "multiple"
                if (attrs["data-range-date"]) dateConfig.mode = "range"
                if (attrs["data-inline-date"]) {
                    dateConfig.inline = true
                    dateConfig.defaultDate = attrs["data-default-date"].value
                }
                if (attrs["data-disable-date"]) {
                    dateConfig.disable = attrs["data-disable-date"].value.split(",")
                }
                if (attrs["data-week-number"]) {
                    dateConfig.weekNumbers = true
                }

                flatpickr(item, dateConfig)
            } else if (type === "timepickr") {
                const timeConfig = {
                    enableTime: true,
                    noCalendar: true,
                    dateFormat: "H:i",
                    defaultDate: new Date(),
                }
                if (attrs["data-time-hrs"]) timeConfig.time_24hr = true
                if (attrs["data-min-time"]) timeConfig.minTime = attrs["data-min-time"].value
                if (attrs["data-max-time"]) timeConfig.maxTime = attrs["data-max-time"].value
                if (attrs["data-default-time"]) timeConfig.defaultDate = attrs["data-default-time"].value
                if (attrs["data-time-inline"]) {
                    timeConfig.inline = true
                    timeConfig.defaultDate = attrs["data-time-inline"].value
                }

                flatpickr(item, timeConfig)
            }
        })
    }



    // Touchspin: plus/minus increment controls
    initTouchSpin() {
        document.querySelectorAll("[data-touchspin]").forEach((spin) => {
            const minusBtn = spin.querySelector("[data-minus]")
            const plusBtn = spin.querySelector("[data-plus]")
            const input = spin.querySelector("input")

            if (input) {
                const min = Number(input.min)
                const max = Number(input.max ?? 0)
                const hasMin = Number.isFinite(min)
                const hasMax = Number.isFinite(max)

                const getValue = () => Number.parseInt(input.value) || 0

                const isReadonly = () => input.hasAttribute("readonly")

                if (!isReadonly()) {
                    if (minusBtn)
                        minusBtn.addEventListener("click", () => {
                            let newVal = getValue() - 1
                            if (!hasMin || newVal >= min) {
                                input.value = newVal.toString()
                            }
                        })

                    if (plusBtn)
                        plusBtn.addEventListener("click", () => {
                            let newVal = getValue() + 1
                            if (!hasMax || newVal <= max) {
                                input.value = newVal.toString()
                            }
                        })
                }
            }
        })
    }
}

class I18nManager {
  constructor({
                defaultLang = 'en',
                langPath = '/static/data/translations/',
                langImageSelector = '#selected-language-image',
                langCodeSelector = '#selected-language-code',
                translationKeySelector = '[data-lang]',
                translationKeyAttribute = 'data-lang',
                languageSelector = '[data-translator-lang]',
              } = {}) {
    this.selectedLanguage = sessionStorage.getItem('__THEME_LANG__') || defaultLang
    this.langPath = langPath
    this.langImageSelector = langImageSelector
    this.langCodeSelector = langCodeSelector
    this.translationKeySelector = translationKeySelector
    this.translationKeyAttribute = translationKeyAttribute
    this.languageSelector = languageSelector

    this.selectedLanguageImage = document.querySelector(this.langImageSelector)
    this.selectedLanguageCode = document.querySelector(this.langCodeSelector)
    this.languageButtons = document.querySelectorAll(this.languageSelector)
  }

  async init(layoutInstance) {

    if (this.selectedLanguage === 'ar') {
      layoutInstance.changeLayoutDirection('rtl');
    }

    await this.applyTranslations()
    this.updateSelectedImage()
    this.updateSelectedCode()
    this.bindLanguageSwitchers(layoutInstance)
  }

  async loadTranslations() {
    try {
      const response = await fetch(`${this.langPath}${this.selectedLanguage}.json`)
      if (!response.ok) throw new Error(`Failed to load ${this.selectedLanguage}.json`)
      return await response.json()
    } catch (err) {
      console.error('Translation load error:', err)
      return {}
    }
  }

  async applyTranslations() {
    const translations = await this.loadTranslations()

    const getNestedValue = (obj, keyPath) => {
      return keyPath.split('.').reduce((acc, key) => acc?.[key] ?? null, obj)
    }

    document.querySelectorAll(this.translationKeySelector).forEach((el) => {
      const key = el.getAttribute(this.translationKeyAttribute)
      const value = getNestedValue(translations, key)
      if (value) {
        el.innerHTML = value
      } else {
        console.warn(`Missing translation for key: ${key}`)
      }
    })
  }

  setLanguage(lang) {
    this.selectedLanguage = lang
    sessionStorage.setItem('__THEME_LANG__', lang)
    this.applyTranslations()
    this.updateSelectedImage()
    this.updateSelectedCode()
  }

  updateSelectedImage() {
    const activeImage = document.querySelector(`[data-translator-lang="${this.selectedLanguage}"] [data-translator-image]`)
    if (activeImage && this.selectedLanguageImage) {
      this.selectedLanguageImage.src = activeImage.src
    }
  }

  updateSelectedCode() {
    if (this.selectedLanguageCode) {
      this.selectedLanguageCode.textContent = this.selectedLanguage.toUpperCase()
    }
  }

  bindLanguageSwitchers(layoutInstance) {
    this.languageButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const lang = button.dataset.translatorLang
        if (lang && lang !== this.selectedLanguage) {
          this.setLanguage(lang)

          if (layoutInstance) {
            const direction = (lang === 'ar') ? 'rtl' : 'ltr';
            layoutInstance.changeLayoutDirection(direction);
          }
        }
      })
    })
  }
}

document.addEventListener("DOMContentLoaded", function (e) {
    new App().init()
    new Plugins().init()
    const layoutCustomizer = new LayoutCustomizer()
    layoutCustomizer.init()

    const i18n = new I18nManager();
    i18n.init(layoutCustomizer);
})

// Chart Color
const theme = (v, a = 1) => {
    const val = getComputedStyle(document.documentElement).getPropertyValue(`--color-${v}`).trim()

    // If no alpha or full opacity, return the color directly
    if (a === 1) return val

    // Convert HEX → RGB
    const hexToRgb = (hex) => {
        const c = hex.replace("#", "")
        const bigint = parseInt(c, 16)
        const r = (bigint >> 16) & 255
        const g = (bigint >> 8) & 255
        const b = bigint & 255
        return `${r}, ${g}, ${b}`
    }

    // Return RGBA if hex or rgb detected
    if (val.startsWith("#")) {
        return `rgba(${hexToRgb(val)}, ${a})`
    } else if (val.startsWith("rgb")) {
        const rgb = val.match(/\d+,\s*\d+,\s*\d+/)?.[0] || val
        return `rgba(${rgb}, ${a})`
    }

    // Fallback
    return val
}

// Debounce function for performance
function debounce(func, wait) {
    let timeout
    return function () {
        clearTimeout(timeout)
        timeout = setTimeout(func, wait)
    }
}

// Updating charts on skin and theme change

// For apexcharts
class CustomApexChart {
    constructor({ selector, series = [], options = {}, colors = [] }) {
        if (!selector) {
            console.warn("CustomApexChart: 'selector' is required.")
            return
        }

        this.selector = selector
        this.series = series
        this.getOptions = options
        this.colors = colors

        if (this.selector instanceof HTMLElement) {
            this.element = this.selector
        } else {
            this.element = document.querySelector(this.selector)
        }

        this.chart = null

        try {
            this.render()
            CustomApexChart.instances.push(this)
        } catch (error) {
            console.error("CustomApexChart: Error during chart initialization:", error)
        }
    }

    getColors() {
        const options = this.getOptions()

        // colors passed in options
        if (options?.colors?.length) {
            return options.colors
        }

        // data-colors from DOM
        if (this.element) {
            const data = this.element.getAttribute("data-colors")
            if (data) {
                const parsed = data
                    .split(",")
                    .map((c) => c.trim())
                    .map((c) => (c.startsWith("#") || c.includes("rgb") ? c : theme(c)))
                if (parsed.length) return parsed
            }
        }

        // default
        return [theme("primary"), theme("secondary"), theme("beta")]
    }

    render() {
        if (this.chart) {
            this.chart.destroy()
        }

        if (this.element) {
            let options = JSON.parse(JSON.stringify(this.getOptions()))

            options.colors = this.getColors()

            options = this.injectDynamicColors(options, options.colors)

            if (!options.series) {
                options.series = this.series
            }

            this.chart = new ApexCharts(this.element, options)
            this.chart.render()
        } else {
            console.warn(`CustomApexChart: No element found for selector '${this.selector}'.`)
        }
    }

    injectDynamicColors(options, colors) {
        // boxPlot colors
        if (options.chart?.type?.toLowerCase() === "boxplot") {
            options.plotOptions = options.plotOptions || {}
            options.plotOptions.boxPlot = options.plotOptions.boxPlot || {}
            options.plotOptions.boxPlot.colors = options.plotOptions.boxPlot.colors || {}
            options.plotOptions.boxPlot.colors.upper = options.plotOptions.boxPlot.colors.upper || colors[0]
            options.plotOptions.boxPlot.colors.lower = options.plotOptions.boxPlot.colors.lower || colors[1]
        }

        // yAxis color styling
        if (Array.isArray(options.yaxis)) {
            options.yaxis.forEach((axis, index) => {
                const color = colors[index] || this.colors[index] || "#999"

                axis.axisBorder = axis.axisBorder || {}
                axis.axisBorder.color = axis.axisBorder.color || color

                axis.labels = axis.labels || {}
                axis.labels.style = axis.labels.style || {}
                axis.labels.style.color = axis.labels.style.color || color
            })
        }

        // marker strokeColor
        if (options.markers && !options.markers.strokeColor) {
            options.markers.strokeColor = colors
        }

        // fill.gradient.gradientToColors
        if (options.fill?.type === "gradient" && options.fill.gradient) {
            options.fill.gradient.gradientToColors = options.fill.gradient.gradientToColors || colors
        }

        // treemap colorScale ranges
        if (options.plotOptions?.treemap?.colorScale?.ranges) {
            const ranges = options.plotOptions.treemap.colorScale.ranges

            if (ranges.length > 0 && !ranges[0].color) {
                ranges[0].color = colors[0]
            }

            if (ranges.length > 1 && !ranges[1].color) {
                ranges[1].color = colors[1]
            }
        }

        return options
    }

    static rerenderAll() {
        if (CustomApexChart.instances.length > 0) {
            for (const instance of CustomApexChart.instances) {
                instance.render()
            }
        }
    }
}

// For echarts
class CustomEChart {
    constructor({ selector, options = {}, theme = null, initOptions = {}, colors = {} }) {
        if (!selector) {
            console.warn("CustomEChart: 'selector' is required.")
            return
        }

        this.selector = selector
        this.element = null
        this.getOptions = options
        this.theme = theme
        this.initOptions = initOptions
        this.chart = null

        try {
            this.render()
            CustomEChart.instances.push(this)
        } catch (err) {
            console.error("CustomEChart: Initialization error", err)
        }
    }

    render() {
        try {
            if (this.selector instanceof HTMLElement) {
                this.element = this.selector
            } else {
                this.element = document.querySelector(this.selector)
            }

            // Dispose existing chart instance
            if (this.chart) {
                this.chart.dispose()
            }

            if (this.element) {
                const resolvedOptions = this.getOptions()

                this.chart = echarts.init(this.element, this.theme, this.initOptions)

                this.chart.setOption(resolvedOptions)

                window.addEventListener(
                    "resize",
                    debounce(() => {
                        this.chart.resize()
                    }, 200)
                )
            } else {
                console.warn(`CustomEChart: No element found for selector '${this.selector}'.`)
            }
        } catch (err) {
            console.error(`CustomEChart: Render error for '${this.selector}'`, err)
        }
    }

    static reSizeAll() {
        if (CustomEChart.instances.length > 0) {
            for (const instance of CustomEChart.instances) {
                if (instance.element && instance.element.offsetParent !== null) {
                    requestAnimationFrame(() => {
                        instance.chart.on("finished", () => {
                            // Use another frame to ensure DOM updates are complete
                            requestAnimationFrame(() => {
                                instance.chart.resize()
                            })
                        })
                    })
                }
            }
        }
    }

    static rerenderAll() {
        if (CustomEChart.instances.length > 0) {
            for (const instance of CustomEChart.instances) {
                instance.render()
            }
        }
    }
}

// For ChartJs
class CustomChartJs {
    static instances = []

    constructor({ selector, options = () => ({}) }) {
        if (!selector) {
            console.warn("CustomChartJs: 'selector' is required.")
            return
        }

        this.selector = selector
        this.getOptions = typeof options === "function" ? options : () => options
        this.element = null
        this.chart = null

        try {
            this.render()
            CustomChartJs.instances.push(this)
        } catch (err) {
            console.error("CustomChartJs: Initialization error", err)
        }
    }

    static getDefaultOptions() {
        const bodyFont = getComputedStyle(document.body).fontFamily.trim()

        return {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: -10,
                },
            },
            scales: {
                x: {
                    ticks: {
                        font: { family: bodyFont },
                        color: [theme("default-400")],
                        display: true,
                        drawTicks: true,
                    },
                    grid: {
                        display: false,
                        drawBorder: false,
                    },
                    border: {
                        display: false, // Hides bottom X axis line
                    },
                },
                y: {
                    ticks: {
                        font: { family: bodyFont },
                        color: [theme("default-400")],
                    },
                    grid: {
                        display: true, // Keeps horizontal lines
                        drawBorder: false, // Hides Y axis border line
                        color: [theme("chart-border-color")],
                        lineWidth: 1,
                    },
                    border: {
                        display: false, // Hides Y axis line (left)
                        dash: [5, 5],
                    },
                },
            },
            plugins: {
                legend: {
                    display: true,
                    position: "top",
                    labels: {
                        font: { family: bodyFont },
                        color: [theme("default-400")],
                        usePointStyle: true, // Show circles instead of default box
                        pointStyle: "circle", // Circle shape
                        boxWidth: 8, // Circle size
                        boxHeight: 8, // (optional) same as width by default
                        padding: 15, // Space between legend items
                    },
                },
                tooltip: {
                    enabled: true,
                    titleFont: { family: bodyFont },
                    bodyFont: { family: bodyFont },
                },
            },
        }
    }

    render() {
        try {
            this.element = this.selector instanceof HTMLElement ? this.selector : document.querySelector(this.selector)

            if (!this.element) {
                console.warn(`CustomChartJs: No element found for selector '${this.selector}'`)
                return
            }

            // Destroy existing chart instance if present
            if (this.chart) {
                this.chart.destroy()
            }

            const { type, data, options, plugins } = this.getOptions()

            // Merge dynamic default options with instance-specific options
            this.chart = new Chart(this.element, {
                type: type || "bar",
                data,
                options: {
                    ...structuredClone(CustomChartJs.getDefaultOptions()),
                    ...(options || {}),
                },
                plugins: plugins || [],
            })

            // Resize listener
            window.addEventListener(
                "resize",
                debounce(() => {
                    if (this.chart) {
                        this.chart.resize()
                    }
                }, 200)
            )
        } catch (err) {
            console.error(`CustomChartJs: Render error for '${this.selector}'`, err)
        }
    }

    static rerenderAll() {
        for (const instance of CustomChartJs.instances) {
            instance.render()
        }
    }

    static reSizeAll() {
        for (const instance of CustomChartJs.instances) {
            if (instance.chart) {
                instance.chart.resize()
            }
        }
    }

    static destroyAll() {
        for (const instance of CustomChartJs.instances) {
            if (instance.chart) {
                instance.chart.destroy()
            }
        }
        CustomChartJs.instances = []
    }
}

// Track instances
CustomApexChart.instances = []
CustomEChart.instances = []
CustomChartJs.instances = []


// Observe theme changes
const themeObserver = new MutationObserver(() => {
    CustomApexChart.rerenderAll()
    CustomEChart.rerenderAll()
    CustomChartJs.rerenderAll()
})

themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-skin", "data-theme", "dir"],
})

// Observe menu size changes
const menuObserver = new MutationObserver(() => {
    requestAnimationFrame(() => {
        CustomEChart.reSizeAll()
    })
})

menuObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-sidenav-size"],
})
