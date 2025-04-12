// Function to get PDF summary
function getPdfSummary() {
    const question = document.getElementById("pdf-question").value;
    fetch("/pdf_summary", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ question: question })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("pdf-summary-result").innerText = data.response || "No summary available.";
    })
    .catch(error => {
        console.error("Error:", error);
        document.getElementById("pdf-summary-result").innerText = "An error occurred.";
    });
}

// Function to generate a quiz
function generateQuiz() {
    const input = document.getElementById("quiz-input").value;
    fetch("/quiz_generator", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ input: input })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("quiz-result").innerText = data.quiz || "No quiz generated.";
    })
    .catch(error => {
        console.error("Error:", error);
        document.getElementById("quiz-result").innerText = "An error occurred.";
    });
}

// Function to generate an image
function generateVisual() {
    const query = document.getElementById("visual-query").value;
    fetch("/visual_generator", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ query: query })
    })
    .then(response => response.json())
    .then(data => {
        if (data.best_image_url) {
            document.getElementById("visual-result").innerHTML = `<img src="${data.best_image_url}" alt="Generated Image" style="max-width: 100%;">`;
        } else {
            document.getElementById("visual-result").innerText = "No suitable image found.";
        }
    })
    .catch(error => {
        console.error("Error:", error);
        document.getElementById("visual-result").innerText = "An error occurred.";
    });
}

// Function to get class summary
function getClassSummary() {
    fetch("/class_summary", {
        method: "GET"
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("class-summary-result").innerText = data.class_summary || "No class summary available.";
    })
    .catch(error => {
        console.error("Error:", error);
        document.getElementById("class-summary-result").innerText = "An error occurred.";
    });
}

let isRecording = false;

function startRecording() {
    if (!isRecording) {
        isRecording = true;
        document.getElementById("start-recording").disabled = true;
        document.getElementById("stop-recording").disabled = false;
        document.getElementById("recording-status").innerText = "Recording status: Started";

        fetch("/start_recording", {
            method: "POST"
        }).then(response => {
            if (!response.ok) {
                throw new Error("Failed to start recording");
            }
            console.log("Recording started");
        }).catch(error => {
            console.error("Error:", error);
            document.getElementById("recording-status").innerText = "Recording status: Error starting recording";
        });
    }
}

function stopRecording() {
    if (isRecording) {
        isRecording = false;
        document.getElementById("start-recording").disabled = false;
        document.getElementById("stop-recording").disabled = true;
        document.getElementById("recording-status").innerText = "Recording status: Stopped";

        fetch("/stop_recording", {
            method: "POST"
        }).then(response => {
            if (!response.ok) {
                throw new Error("Failed to stop recording");
            }
            console.log("Recording stopped");
        }).catch(error => {
            console.error("Error:", error);
            document.getElementById("recording-status").innerText = "Recording status: Error stopping recording";
        });
    }
}