// Theme persistence, dashboard feedback, charts, and landing animation.
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initUploadFeedback();
    initScoreChart();
    initHeroScene();
});

function initTheme() {
    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");
    const savedTheme = localStorage.getItem("resumeParserTheme") || "light";

    root.setAttribute("data-bs-theme", savedTheme);
    if (!themeToggle) return;

    themeToggle.textContent = savedTheme === "dark" ? "Light mode" : "Dark mode";
    themeToggle.addEventListener("click", () => {
        const nextTheme = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-bs-theme", nextTheme);
        localStorage.setItem("resumeParserTheme", nextTheme);
        themeToggle.textContent = nextTheme === "dark" ? "Light mode" : "Dark mode";
    });
}

function initUploadFeedback() {
    const uploadForm = document.getElementById("uploadForm");
    if (!uploadForm) return;

    uploadForm.addEventListener("submit", () => {
        const button = uploadForm.querySelector("button[type='submit']");
        const spinner = button.querySelector(".spinner-border");
        const label = button.querySelector(".button-label");
        const loadingText = document.getElementById("loadingText");

        button.disabled = true;
        spinner.classList.remove("d-none");
        label.textContent = "Parsing...";
        loadingText.classList.remove("d-none");
    });
}

function initScoreChart() {
    const canvas = document.getElementById("scoreChart");
    if (!canvas || !window.Chart) return;

    const labels = JSON.parse(canvas.dataset.labels || "[]").reverse();
    const scores = JSON.parse(canvas.dataset.scores || "[]").reverse();
    const empty = scores.length === 0;

    new Chart(canvas, {
        type: "line",
        data: {
            labels: empty ? ["No resumes"] : labels,
            datasets: [{
                label: "Resume score",
                data: empty ? [0] : scores,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.16)",
                fill: true,
                tension: 0.35,
                pointRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, max: 100 },
                x: { ticks: { maxRotation: 0, autoSkip: true } },
            },
        },
    });
}

function initHeroScene() {
    const canvas = document.getElementById("heroCanvas");
    if (!canvas || !window.THREE) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 0.3, 8);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    const group = new THREE.Group();
    scene.add(group);

    const geometry = new THREE.IcosahedronGeometry(2.1, 2);
    const material = new THREE.MeshStandardMaterial({
        color: 0x5eead4,
        wireframe: true,
        transparent: true,
        opacity: 0.34,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(2.7, 0.1, 0);
    group.add(mesh);

    const pointsGeometry = new THREE.BufferGeometry();
    const positions = [];
    for (let i = 0; i < 420; i += 1) {
        positions.push((Math.random() - 0.5) * 14, (Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8);
    }
    pointsGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const points = new THREE.Points(
        pointsGeometry,
        new THREE.PointsMaterial({ color: 0x93c5fd, size: 0.025, transparent: true, opacity: 0.78 })
    );
    group.add(points);

    scene.add(new THREE.AmbientLight(0xffffff, 0.85));
    const light = new THREE.PointLight(0xffedd5, 2.1);
    light.position.set(-3, 4, 5);
    scene.add(light);

    if (window.gsap) {
        gsap.from(".hero-content > *", { y: 24, opacity: 0, duration: 0.8, stagger: 0.12, ease: "power3.out" });
        gsap.from(".metric-tile", { y: 16, opacity: 0, duration: 0.7, stagger: 0.08, delay: 0.4 });
    }

    function animate() {
        mesh.rotation.x += 0.0025;
        mesh.rotation.y += 0.004;
        points.rotation.y -= 0.0008;
        renderer.render(scene, camera);
        requestAnimationFrame(animate);
    }
    animate();

    window.addEventListener("resize", () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}
