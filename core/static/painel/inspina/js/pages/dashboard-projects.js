/**
 * Template Name: Inspinia - Admin & Dashboard Template
 * By (Author): WebAppLayers
 * Module/App (File Name): Projects Dashboard
 * 
*/

const xLabels = Array.from({ length: 15 }, (_, i) => `Day ${i + 1}`)

new CustomEChart({
    selector: "#revenue-chart",
    options: () => ({
        textStyle: {
            fontFamily: getComputedStyle(document.body).fontFamily,
        },
        tooltip: {
            trigger: "axis",
            padding: [5, 0],
            backgroundColor: theme("card"),
            borderColor: theme("default-200"),
            textStyle: { color: theme("default-600") },
            borderWidth: 1,
            transitionDuration: 0.125,
            axisPointer: { type: "none" },
            shadowBlur: 2,
            shadowColor: "rgba(76, 76, 92, 0.15)",
            shadowOffsetX: 0,
            shadowOffsetY: 1, // Custom HTML formatter
            formatter: function (params) {
                const title = params[0].name // xAxis label
                let content = `<div style="font-size: 14px; font-weight: 600; text-transform: uppercase; border-bottom: 1px solid ${theme("default-200")}; margin-bottom: 8px; padding: 3px 10px 8px;">${title}</div>`
                params.forEach((item) => {
                    content += `<div style="margin-top: 4px; padding: 3px 15px;">
                            <span style="display:inline-block;margin-right:5px;border-radius:50%;width:10px;height:10px;background-color:${item.color};"></span>
                            ${item.seriesName} : <strong>${item.value}</strong>
                        </div>`
                })
                return content
            },
        },
        xAxis: {
            type: "category",
            data: xLabels,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: theme("default-100"),
                    type: "dashed",
                },
            },
            axisTick: {
                show: false,
            },
            axisLabel: {
                color: theme("body-color"),
                margin: 15,
            },
            splitLine: {
                show: false,
            },
        },
        yAxis: {
            type: "value",
            splitLine: {
                lineStyle: {
                    color: theme("default-200"),
                    type: "dashed",
                },
            },
            boundaryGap: false,
            axisLabel: {
                show: true,
                color: theme("body-color"),
                margin: 15,
            },
            axisTick: {
                show: false,
            },
            axisLine: {
                show: false,
            },
        },
        series: [
            {
                name: "Total Revenue",
                type: "line",
                smooth: true,
                symbolSize: 2,
                itemStyle: {
                    color: theme("primary"),
                    borderColor: theme("primary"),
                    borderWidth: 2,
                },
                areaStyle: {
                    opacity: 0.2,
                    color: theme("primary"),
                },
                lineStyle: {
                    color: theme("primary"),
                },
                symbol: "circle",
                stack: "data",
                data: [45, 88, 120, 160, 210, 240, 350, 420, 380, 500, 640, 710, 890, 1150, 1200],
            },
            {
                name: "Orders",
                type: "line",
                smooth: true,
                symbolSize: 2,
                itemStyle: {
                    color: theme("secondary"),
                    borderColor: theme("secondary"),
                    borderWidth: 2,
                },
                areaStyle: {
                    opacity: 0.2,
                    color: theme("secondary"),
                },
                lineStyle: {
                    color: theme("secondary"),
                },
                symbol: "circle",
                stack: "data",
                data: [15, 30, 35, 50, 55, 75, 95, 120, 135, 160, 180, 210, 250, 390, 450],
            },
        ],
        grid: {
            right: 20,
            left: 5,
            bottom: 5,
            top: 8,
            containLabel: true,
        },
    }),
})

new CustomEChart({
    selector: "#project-progress-chart",
    options: () => ({
        tooltip: {
            trigger: "item",
            padding: [8, 15],
            backgroundColor: theme("card"),
            borderColor: theme("default-200"),
            textStyle: { color: theme("default-600") },
            borderWidth: 1,
            transitionDuration: 0.125,
            axisPointer: { type: "none" },
            shadowBlur: 2,
            shadowColor: "rgba(76, 76, 92, 0.15)",
            shadowOffsetX: 0,
            shadowOffsetY: 1,
        },
        textStyle: {
            fontFamily: getComputedStyle(document.body).fontFamily,
        },
        series: [
            {
                name: "Project Progress",
                type: "pie",
                radius: [60, 100],
                center: ["50%", "50%"],
                roseType: "area",
                itemStyle: {
                    borderRadius: 8,
                },
                label: {
                    color: theme("body-color"),
                },
                data: [
                    { value: 85, name: "Website Redesign", itemStyle: { color: theme("chart-primary") } },
                    {
                        value: 70,
                        name: "Mobile App",
                        itemStyle: { color: theme("secondary") },
                    },
                    { value: 55, name: "CRM Integration", itemStyle: { color: theme("info") } },
                    {
                        value: 60,
                        name: "Product Launch",
                        itemStyle: { color: theme("success") },
                    },
                    { value: 75, name: "Backend Refactor", itemStyle: { color: theme("light") } },
                    {
                        value: 50,
                        name: "Client Dashboard",
                        itemStyle: { color: theme("warning") },
                    },
                ],
            },
        ],
    }),
})

// Function to generate random charity data
function generateRandomData() {
    const charityNames = ["Charity A", "Charity B", "Charity C"]
    const randomData = charityNames.map((name) => ({
        name: name,
        value: Math.floor(Math.random() * 100) + 1,
    }))
    const total = randomData.reduce((sum, item) => sum + item.value, 0)
    randomData.forEach((item) => {
        item.value = (item.value / total) * 100
    })
    return randomData
}

function initDonutChart(element) {
    const charityData = generateRandomData()

    new CustomEChart({
        selector: element,
        options: () => ({
            tooltip: { show: false },
            series: [
                {
                    type: "pie",
                    radius: ["60%", "100%"],
                    hoverAnimation: false,
                    label: { show: false },
                    labelLine: { show: false },
                    data: charityData.map((item, index) => ({
                        value: item.value,
                        itemStyle: {
                            color: index === 0 ? theme("primary") : index === 1 ? theme("secondary") : "#bbcae14d",
                        },
                    })),
                },
            ],
        }),
    })
}

const donutCharts = document.querySelectorAll(".donut-chart")
if (donutCharts) {
    donutCharts.forEach(initDonutChart)
}
