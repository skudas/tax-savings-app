// Main JavaScript for Tax Savings MVP

// API base URL
const API_BASE = '/api';

// Resolve a safe post-auth destination from the ?redirect= query param
function destinationAfterAuth() {
    const redirect = new URLSearchParams(window.location.search).get('redirect');
    if (!redirect) return '/marketplace/browse.html';
    try {
        const url = new URL(redirect, window.location.origin);
        if (url.origin !== window.location.origin) return '/marketplace/browse.html';
        return `${url.pathname}${url.search}${url.hash}`;
    } catch (error) {
        return '/marketplace/browse.html';
    }
}

// Check if user is authenticated on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
});

// Check authentication status
async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`);
        if (response.ok) {
            const user = await response.json();
            showAuthenticatedUI(user);
        } else {
            showUnauthenticatedUI();
        }
    } catch (error) {
        showUnauthenticatedUI();
    }
}

// Update UI for authenticated user
function showAuthenticatedUI(user) {
    const authNav = document.getElementById('nav-auth');
    const userNav = document.getElementById('nav-user');
    const userEmail = document.getElementById('user-email');

    if (authNav) authNav.style.display = 'none';
    if (userNav) {
        userNav.style.display = 'block';
        if (userEmail) userEmail.textContent = user.email;
    }
}

// Update UI for unauthenticated user
function showUnauthenticatedUI() {
    const authNav = document.getElementById('nav-auth');
    const userNav = document.getElementById('nav-user');

    if (authNav) authNav.style.display = 'block';
    if (userNav) userNav.style.display = 'none';
}

// Logout function
async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST' });
        showUnauthenticatedUI();
        window.location.href = '/';
    } catch (error) {
        console.error('Logout failed:', error);
        alert('Logout failed');
    }
}

// Form submission handler for signup
async function handleSignup(event) {
    event.preventDefault();

    const formData = {
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        first_name: document.getElementById('first_name').value,
        last_name: document.getElementById('last_name').value,
    };

    try {
        const response = await fetch(`${API_BASE}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            window.location.href = `/auth/login.html${destinationAfterAuth() === '/marketplace/browse.html' ? '' : `?redirect=${encodeURIComponent(destinationAfterAuth())}`}`;
        } else {
            const error = await response.json();
            alert(`Sign up failed: ${error.detail}`);
        }
    } catch (error) {
        alert('Sign up failed: ' + error.message);
    }
}

// Form submission handler for login
async function handleLogin(event) {
    event.preventDefault();

    const formData = {
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
    };

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            window.location.href = destinationAfterAuth();
        } else {
            const error = await response.json();
            alert(`Login failed: ${error.detail}`);
        }
    } catch (error) {
        alert('Login failed: ' + error.message);
    }
}

// Form submission for onboarding questionnaire
async function handleOnboarding(event) {
    event.preventDefault();

    const formData = {
        annual_net_profit: parseFloat(document.getElementById('profit').value),
        current_entity_type: document.getElementById('entity_type').value,
        state: document.getElementById('state').value,
        pays_payroll_provider: document.getElementById('payroll').checked,
    };

    try {
        const response = await fetch(`${API_BASE}/onboarding/questionnaire`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const result = await response.json();
            displayResults(result);
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (error) {
        alert('Submission failed: ' + error.message);
    }
}

// Display onboarding results
function displayResults(result) {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;

    const html = `
        <div class="alert alert-success">
            <h3>S-Corp Savings Estimate</h3>
            <p><strong>Annual Net Profit:</strong> $${result.annual_net_profit.toLocaleString()}</p>
            <p><strong>Current SE Tax (${result.current_entity_type}):</strong> $${result.current_se_tax_annual.toLocaleString()}</p>
            <p><strong>Recommended W-2 Salary:</strong> $${result.recommended_w2_salary.toLocaleString()}</p>
            <p><strong>SE Tax with S-Corp:</strong> $${result.estimated_se_tax_with_scorp.toLocaleString()}</p>
            <p><strong>Gross Tax Savings:</strong> $${result.gross_tax_savings.toLocaleString()}</p>
            <p><strong>Annual S-Corp Costs:</strong> $${result.estimated_annual_costs.toLocaleString()}</p>
            <p style="font-size: 1.25rem;"><strong>Net Annual Savings:</strong> $${result.net_annual_savings.toLocaleString()}</p>
            <p><em>Range: $${result.net_annual_savings_min.toLocaleString()} - $${result.net_annual_savings_max.toLocaleString()}</em></p>
        </div>

        <div class="alert alert-info">
            <h4>Assumptions</h4>
            <ul>
                <li>Federal SE Tax Rate: ${(result.assumptions.federal_se_tax_rate * 100).toFixed(1)}%</li>
                <li>Reasonable Salary: ${(result.assumptions.reasonable_salary_percent * 100).toFixed(0)}% of net profit</li>
                <li>Annual S-Corp Costs: $${result.assumptions.annual_scorp_costs.total.toLocaleString()}</li>
                <li>Annual Filing: $${result.assumptions.annual_scorp_costs.annual_filing}</li>
                <li>Accounting: $${result.assumptions.annual_scorp_costs.accounting}</li>
                <li>Payroll: $${result.assumptions.annual_scorp_costs.payroll}</li>
            </ul>
            <p style="margin-top: 1rem; font-weight: bold;">⚠️ This is an estimate. Consult a CPA before implementing S-Corp election.</p>
        </div>
    `;

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
}

// Upload transactions via CSV
async function handleTransactionUpload(event) {
    event.preventDefault();

    const fileInput = document.getElementById('csv_file');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select a file');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/dashboard/transactions/upload`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            alert(`Uploaded ${result.uploaded_count} transactions`);
            loadTransactions();
        } else {
            const error = await response.json();
            alert(`Upload failed: ${error.detail}`);
        }
    } catch (error) {
        alert('Upload failed: ' + error.message);
    }
}

// Load and display transactions
async function loadTransactions() {
    try {
        const response = await fetch(`${API_BASE}/dashboard/transactions`);
        if (response.ok) {
            const transactions = await response.json();
            displayTransactions(transactions);
        }
    } catch (error) {
        console.error('Failed to load transactions:', error);
    }
}

// Display transactions in table
function displayTransactions(transactions) {
    const container = document.getElementById('transactions');
    if (!container) return;

    if (transactions.length === 0) {
        container.innerHTML = '<p>No transactions yet. Upload a CSV file to get started.</p>';
        return;
    }

    let html = '<table><thead><tr><th>Date</th><th>Amount</th><th>Description</th><th>Category</th></tr></thead><tbody>';

    for (const txn of transactions) {
        const dateObj = new Date(txn.date);
        const dateStr = dateObj.toLocaleDateString();
        html += `
            <tr>
                <td>${dateStr}</td>
                <td>$${Math.abs(txn.amount).toLocaleString()}</td>
                <td>${txn.description}</td>
                <td>${txn.category_name || 'Uncategorized'}</td>
            </tr>
        `;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
}

// Load monthly summary
async function loadMonthlySummary() {
    try {
        const response = await fetch(`${API_BASE}/dashboard/summary`);
        if (response.ok) {
            const summary = await response.json();
            displaySummary(summary);
        }
    } catch (error) {
        console.error('Failed to load summary:', error);
    }
}

// Display monthly summary
function displaySummary(summary) {
    const container = document.getElementById('summary');
    if (!container) return;

    if (summary.length === 0) {
        container.innerHTML = '<p>No transactions to summarize.</p>';
        return;
    }

    let html = '<table><thead><tr><th>Month</th><th>Income</th><th>Expenses</th><th>Net</th></tr></thead><tbody>';

    for (const item of summary) {
        const netClass = item.net >= 0 ? 'positive' : 'negative';
        html += `
            <tr>
                <td>${item.month}</td>
                <td>$${item.income.toLocaleString()}</td>
                <td>$${item.expenses.toLocaleString()}</td>
                <td class="${netClass}">$${item.net.toLocaleString()}</td>
            </tr>
        `;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
}
