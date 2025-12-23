let sessionId = "session_" + Math.floor(Math.random() * 100000);
let started = false;
async function loadCustomers() {
    const response = await fetch("/customers");
    const customers = await response.json();

    const dropdown = document.getElementById("customer-dropdown");

    customers.forEach(c => {
        const option = document.createElement("option");
        option.value = c.id;
        option.text = c.name;
        dropdown.appendChild(option);
    });
}

window.onload = loadCustomers;

async function startCall() {
    const dropdown = document.getElementById("customer-dropdown");
    const customerId = dropdown.value;

    if (!customerId) {
        alert("Please select a customer first");
        return;
    }

    sessionId = "session_" + Math.floor(Math.random() * 100000);
    started = true;

    const response = await fetch("/bot/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: sessionId,
            customer_id: parseInt(customerId)
        })
    });

    const data = await response.json();
    addMessage(
        `${data.reply}\n⏱️ Latency: ${data.latency_ms} ms`,
        "bot"
    );


}


function addMessage(text, sender) {
    const chatBox = document.getElementById("chat-box");
    const msg = document.createElement("div");
    msg.className = `message ${sender}`;
    msg.innerText = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function handleKey(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, "user");
    input.value = "";

    let url, payload;

    if (!started) {
        url = "/bot/start";
        payload = {
            session_id: sessionId,
            customer_id: 1   // change later (DB-driven)
        };
    } else {
        url = "/bot/reply";
        payload = {
            session_id: sessionId,
            message: message
        };
    }

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        addMessage(
            `${data.reply}\n⏱️ Latency: ${data.latency_ms} ms`,
            "bot"
        );


        started = true;

    } catch (error) {
        addMessage("Something went wrong. Please try again.", "bot");
    }
}
