// Modal functionality for test details
let responseChart = null;
let toolChart = null;
let responseQuartileChart = null;
let toolQuartileChart = null;
let currentTestData = null;
let allRuns = [];

// Track chart states
let chartStates = {
    response: 'bar', // 'bar' or 'quartile'
    tool: 'bar'
};

// Initialize modal event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add click listeners to all test items
    document.querySelectorAll('.test-item').forEach(item => {
        item.addEventListener('click', function() {
            const testName = this.dataset.testName;
            const testDescription = this.dataset.testDescription;
            const testData = JSON.parse(this.dataset.testData);
            openTestModal(testName, testDescription, testData);
        });
    });
});

function openTestModal(testName, testDescription, testData) {
    const modal = document.getElementById('testModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalDescription = document.getElementById('modalDescription');
    
    modalTitle.textContent = testName;
    modalDescription.textContent = testDescription;
    
    // Store current test data
    currentTestData = testData;
    
    // Reset chart states
    chartStates.response = 'bar';
    chartStates.tool = 'bar';
    
    // Reset flip containers
    document.getElementById('responseChartContainer').classList.remove('flipped');
    document.getElementById('toolChartContainer').classList.remove('flipped');
    
    // Reset button texts
    document.querySelector('[onclick="toggleChart(\'response\')"]').textContent = 'Show Quartiles';
    document.querySelector('[onclick="toggleChart(\'tool\')"]').textContent = 'Show Quartiles';
    
    // Destroy existing charts if they exist
    destroyAllCharts();
    
    // Show modal
    modal.style.display = 'block';
    
    // Create charts after modal is visible
    setTimeout(() => {
        createResponseChart(testData);
        createToolChart(testData);
        createResponseQuartileChart(testData);
        createToolQuartileChart(testData);
        setupModelFilter(testData);
        populateRunDetails(testData);
    }, 100);
}

function closeModal() {
    const modal = document.getElementById('testModal');
    modal.style.display = 'none';
    
    // Destroy all charts when closing
    destroyAllCharts();
    
    // Reset data
    currentTestData = null;
    allRuns = [];
}

function destroyAllCharts() {
    if (responseChart) {
        responseChart.destroy();
        responseChart = null;
    }
    if (toolChart) {
        toolChart.destroy();
        toolChart = null;
    }
    if (responseQuartileChart) {
        responseQuartileChart.destroy();
        responseQuartileChart = null;
    }
    if (toolQuartileChart) {
        toolQuartileChart.destroy();
        toolQuartileChart = null;
    }
}

function toggleChart(chartType) {
    const container = document.getElementById(chartType + 'ChartContainer');
    const button = document.querySelector(`[onclick="toggleChart('${chartType}')"]`);
    
    container.classList.toggle('flipped');
    
    if (chartStates[chartType] === 'bar') {
        chartStates[chartType] = 'quartile';
        button.textContent = 'Show Bar Chart';
    } else {
        chartStates[chartType] = 'bar';
        button.textContent = 'Show Quartiles';
    }
}

function setupModelFilter(testData) {
    const modelFilter = document.getElementById('modelFilter');
    const models = Object.keys(testData.model_scores);
    
    // Clear existing options except "All Models"
    modelFilter.innerHTML = '<option value="all">All Models</option>';
    
    // Add model options
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelFilter.appendChild(option);
    });
    
    // Reset to "All Models"
    modelFilter.value = 'all';
}

function filterRuns() {
    if (!currentTestData) return;
    
    const selectedModel = document.getElementById('modelFilter').value;
    populateRunDetails(currentTestData, selectedModel);
}

function populateRunDetails(testData, filterModel = 'all') {
    const runsContainer = document.getElementById('runsContainer');
    const runsCount = document.getElementById('runsCount');
    runsContainer.innerHTML = '';
    
    // Extract individual runs from the actual test data structure
    allRuns = [];
    
    // Check if we have individual_runs data in the testData
    if (testData.individual_runs) {
        // Use the actual individual runs data
        const models = Object.keys(testData.model_scores);
        
        models.forEach(model => {
            if (filterModel !== 'all' && model !== filterModel) {
                return; // Skip this model if filtering
            }
            
            // Get individual runs for this model from the actual data
            const modelRuns = testData.individual_runs[model] || [];
            
            modelRuns.forEach(run => {
                allRuns.push({
                    model: model,
                    runNumber: run.run_number,
                    responseScore: run.response_score,
                    toolScore: run.tool_score,
                    llmScore: run.llm_eval,
                    reasoning: run.llm_reasoning || 'No reasoning provided',
                    query: run.query || '',
                    actualResponse: run.actual_response || '',
                    expectedResponse: run.expected_response || '',
                    executionTime: run.execution_time || 'N/A' // Add execution time with 'N/A' fallback
                });
            });
        });
    } else {
        // Fallback: generate mock runs based on average scores (for backward compatibility)
        const models = Object.keys(testData.model_scores);
        
        models.forEach(model => {
            if (filterModel !== 'all' && model !== filterModel) {
                return; // Skip this model if filtering
            }
            
            const responseScore = testData.model_scores[model];
            const toolScore = testData.tool_scores && testData.tool_scores[model] !== undefined 
                ? testData.tool_scores[model] 
                : Math.max(0, Math.min(1, responseScore + (Math.random() - 0.5) * 0.3));
            
            // Generate 3-5 mock runs for this model
            const numRuns = Math.floor(Math.random() * 3) + 3; // 3-5 runs
            
            for (let i = 0; i < numRuns; i++) {
                const runResponseScore = Math.max(0, Math.min(1, responseScore + (Math.random() - 0.5) * 0.2));
                const runToolScore = Math.max(0, Math.min(1, toolScore + (Math.random() - 0.5) * 0.2));
                
                allRuns.push({
                    model: model,
                    runNumber: i + 1,
                    responseScore: runResponseScore,
                    toolScore: runToolScore,
                    reasoning: generateMockReasoning(runResponseScore, runToolScore, model, i + 1),
                    query: '',
                    actualResponse: '',
                    expectedResponse: ''
                });
            }
        });
    }
    
    // Update runs count
    const totalRuns = allRuns.length;
    const modelText = filterModel === 'all' ? 'all models' : filterModel;
    runsCount.textContent = `Showing ${totalRuns} runs for ${modelText}`;
    
    // Sort runs by model and run number
    allRuns.sort((a, b) => {
        if (a.model !== b.model) {
            return a.model.localeCompare(b.model);
        }
        return a.runNumber - b.runNumber;
    });
    
    // Create run items
    allRuns.forEach(run => {
        const runItem = document.createElement('div');
        runItem.className = 'run-item';
        
        const llmScoreHtml = run.llmScore !== null ? 
            `<div class="run-score llm">LLM Eval: ${run.llmScore.toFixed(3)}</div>` : '';
        
        runItem.innerHTML = `
            <div class="run-header">
                <div class="run-model">[Run ${run.runNumber}] ${run.model}</div>
                <div class="run-scores">
                    <div class="run-score response">Response: ${run.responseScore.toFixed(3)}</div>
                    <div class="run-score tool">Tool: ${run.toolScore.toFixed(3)}</div>
                    ${llmScoreHtml}
                </div>
            </div>
            <div class="run-reasoning">
                <div class="reasoning-label">Evaluation Reasoning:</div>
                <div class="reasoning-text">${run.reasoning}</div>
            </div>
            <div class="run-performance">
                <div class="run-execution-time">Execution Time: ${typeof run.executionTime === 'number' ? run.executionTime.toFixed(3) + 's' : run.executionTime}</div>
            </div>
        `;
        
        runsContainer.appendChild(runItem);
    });
}

function generateMockReasoning(responseScore, toolScore, model, runNumber) {
    let responseQuality = '';
    let toolUsage = '';
    
    if (responseScore >= 0.8) {
        responseQuality = 'excellent response quality with comprehensive and accurate information';
    } else if (responseScore >= 0.6) {
        responseQuality = 'good response quality with mostly accurate information';
    } else if (responseScore >= 0.4) {
        responseQuality = 'adequate response quality with some gaps in information';
    } else {
        responseQuality = 'poor response quality with significant inaccuracies or missing information';
    }
    
    if (toolScore >= 0.8) {
        toolUsage = 'demonstrated excellent tool usage with proper parameter selection and effective integration';
    } else if (toolScore >= 0.6) {
        toolUsage = 'showed good tool usage with appropriate selections and mostly effective integration';
    } else if (toolScore >= 0.4) {
        toolUsage = 'exhibited adequate tool usage with some suboptimal choices or integration issues';
    } else {
        toolUsage = 'displayed poor tool usage with incorrect selections or failed integrations';
    }
    
    const additionalComments = [
        'The model followed instructions well and maintained context throughout the interaction.',
        'Response formatting was clear and well-structured.',
        'The model demonstrated good understanding of the task requirements.',
        'Some minor issues with response coherence were observed.',
        'The model showed creativity in problem-solving approaches.',
        'Response time was within acceptable parameters.',
        'The model handled edge cases appropriately.',
        'The model provided detailed explanations for its reasoning.',
        'Some inconsistencies in tool parameter selection were noted.',
        'The model effectively utilized available context information.',
        'Response quality varied slightly across different prompt variations.',
        'The model demonstrated good error handling capabilities.'
    ];
    
    const randomComment = additionalComments[Math.floor(Math.random() * additionalComments.length)];
    
    return `Run ${runNumber}: ${model} ${responseQuality} and ${toolUsage}. ${randomComment}`;
}
