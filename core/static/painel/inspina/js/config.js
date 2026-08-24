(function () {
        const html = document.documentElement
        const storageKey = "__THEME_CONFIG__"
        const savedConfig = sessionStorage.getItem(storageKey)

        // Default config
        const defaultConfig = {
    "dir": "ltr",
    "skin": "default",
    "theme": "light",
    "width": "fluid",
    "position": "fixed",
    "orientation": "vertical",
    "sidenav-size": "default",
    "sidenav-user": true,
    "topbar-color": "light",
    "sidenav-color": "dark"
}

        // Build config from HTML attributes
        function getSystemTheme() {
            return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
        }

        // Build config from HTML attributes
        const htmlConfig = {
            dir: html.getAttribute("dir") || defaultConfig.dir,
            skin: html.getAttribute("data-skin") || defaultConfig.skin,
            theme: html.getAttribute("data-theme") === "system" ? getSystemTheme() : html.getAttribute("data-theme") || (defaultConfig["theme"] === "system" ? getSystemTheme() : defaultConfig["theme"]),
            "topbar-color": html.getAttribute("data-topbar-color") || defaultConfig["topbar-color"],
            "sidenav-color": html.getAttribute("data-menu-color") || defaultConfig['sidenav-color'],
            "sidenav-size": html.getAttribute("data-sidenav-size") || defaultConfig['sidenav-size'],
            "sidenav-user": html.hasAttribute('data-sidenav-user') || defaultConfig['sidenav-user'],
            position: html.getAttribute('data-layout-position') || defaultConfig['position'],
            width: html.getAttribute('data-layout-width') || defaultConfig['width'],
            monochrome: html.classList.contains("monochrome") || defaultConfig.monochrome || false,
        }

        // Save merged config as defaults globally
        window.defaultConfig = structuredClone(htmlConfig)

        // Load from session if exists
        let config = savedConfig ? JSON.parse(savedConfig) : htmlConfig
        window.config = config

        // Apply layout attributes immediately
        html.setAttribute("dir", config.dir)
        html.setAttribute("data-skin", config.skin)
        html.setAttribute("data-theme", config.theme)
        html.setAttribute("data-topbar-color", config["topbar-color"])
        html.setAttribute("data-menu-color", config["sidenav-color"])
        html.setAttribute('data-layout-position', config['position'])
        html.setAttribute('data-layout-width', config['width'])
        html.classList.toggle("monochrome", config.monochrome);

        if (config['sidenav-user'] === true) {
            html.setAttribute('data-sidenav-user', 'true')
        } else {
            html.removeAttribute('data-sidenav-user')
        }

        if (config['sidenav-size']) {
            let size = config['sidenav-size']

            if (window.innerWidth <= 1140) {
                size = "offcanvas"
            }

            html.setAttribute("data-sidenav-size", size)
        }
    })()