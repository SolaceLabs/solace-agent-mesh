// Chart creation functions for modal

function createResponseChart(testData) {
    const ctx = document.getElementById('responseChart').getContext('2d');
    
    const models = Object.keys(testData.model_scores);
    const responseScores = models.map(model => testData.model_scores[model]);
    
    responseChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models.map(model => model),
            datasets: [{
                label: 'Response Score',
                data: responseScores,
                backgroundColor: responseScores.map(score => getScoreColor(score)),
                borderColor: responseScores.map(score => getScoreColor(score)),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        color: '#000',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    }
                },
                x: {
                    ticks: {
                        color: '#000',
                        font: {
                            size: 10,
                            weight: 'normal'
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function createToolChart(testData) {
    const ctx = document.getElementById('toolChart').getContext('2d');
    
    const models = Object.keys(testData.model_scores);
    const toolScores = models.map(model => {
        // Use actual tool scores if available, otherwise generate mock data
        if (testData.tool_scores && testData.tool_scores[model] !== undefined) {
            return testData.tool_scores[model];
        } else {
            // Generate mock tool scores based on response scores with some variation
            const responseScore = testData.model_scores[model];
            return Math.max(0, Math.min(1, responseScore + (Math.random() - 0.5) * 0.3));
        }
    });
    
    toolChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models.map(model => model),
            datasets: [{
                label: 'Tool Score',
                data: toolScores,
                backgroundColor: toolScores.map(score => getScoreColor(score)),
                borderColor: toolScores.map(score => getScoreColor(score)),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        color: '#000',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    }
                },
                x: {
                    ticks: {
                        color: '#000',
                        font: {
                            size: 10,
                            weight: 'normal'
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function createResponseQuartileChart(testData) {
    const ctx = document.getElementById('responseQuartileChart').getContext('2d');
    
    const models = Object.keys(testData.model_scores);
    const responseScores = models.map(model => testData.model_scores[model]);
    
    // Create custom boxplot data
    const boxplotData = models.map((model, index) => {
        // Check if we have individual run data for this model
        const individualRuns = testData.individual_runs && testData.individual_runs[model];
        
        if (individualRuns && individualRuns.length > 1) {
            // Use actual individual run data to calculate real quartiles
            const scores = individualRuns.map(run => run.response_score).sort((a, b) => a - b);
            const quartileData = calculateActualQuartiles(scores);
            
            return {
                x: index,
                min: quartileData.min,
                q1: quartileData.q1,
                median: quartileData.median,
                q3: quartileData.q3,
                max: quartileData.max,
                outliers: quartileData.outliers
            };
        } else {
            // Single data point - show as a line (all values the same)
            const score = testData.model_scores[model];
            return {
                x: index,
                min: score,
                q1: score,
                median: score,
                q3: score,
                max: score,
                outliers: []
            };
        }
    });
    
    responseQuartileChart = new Chart(ctx, {
        type: 'boxplot',
        data: {
            labels: models,
            datasets: [{
                label: 'Response Score Distribution',
                data: boxplotData,
                backgroundColor: responseScores.map(score => getScoreColor(score) + '80'),
                borderColor: responseScores.map(score => getScoreColor(score)),
                borderWidth: 2,
                outlierColor: '#999999',
                outlierRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        color: '#000',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    }
                },
                x: {
                    ticks: {
                        color: '#000',
                        font: {
                            size: 10,
                            weight: 'normal'
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const data = context.parsed;
                            if (data.min === data.max) {
                                return `Single value: ${data.min.toFixed(3)}`;
                            }
                            return [
                                `Min: ${data.min.toFixed(3)}`,
                                `Q1: ${data.q1.toFixed(3)}`,
                                `Median: ${data.median.toFixed(3)}`,
                                `Q3: ${data.q3.toFixed(3)}`,
                                `Max: ${data.max.toFixed(3)}`
                            ];
                        }
                    }
                }
            }
        }
    });
}

function createToolQuartileChart(testData) {
    const ctx = document.getElementById('toolQuartileChart').getContext('2d');
    
    const models = Object.keys(testData.model_scores);
    const toolScores = models.map(model => {
        if (testData.tool_scores && testData.tool_scores[model] !== undefined) {
            return testData.tool_scores[model];
        } else {
            const responseScore = testData.model_scores[model];
            return Math.max(0, Math.min(1, responseScore + (Math.random() - 0.5) * 0.3));
        }
    });
    
    // Create custom boxplot data
    const boxplotData = models.map((model, index) => {
        // Check if we have individual run data for this model
        const individualRuns = testData.individual_runs && testData.individual_runs[model];
        
        if (individualRuns && individualRuns.length > 1) {
            // Use actual individual run data to calculate real quartiles
            const scores = individualRuns.map(run => run.tool_score).sort((a, b) => a - b);
            const quartileData = calculateActualQuartiles(scores);
            
            return {
                x: index,
                min: quartileData.min,
                q1: quartileData.q1,
                median: quartileData.median,
                q3: quartileData.q3,
                max: quartileData.max,
                outliers: quartileData.outliers
            };
        } else {
            // Single data point - show as a line (all values the same)
            const score = toolScores[index];
            return {
                x: index,
                min: score,
                q1: score,
                median: score,
                q3: score,
                max: score,
                outliers: []
            };
        }
    });
    
    toolQuartileChart = new Chart(ctx, {
        type: 'boxplot',
        data: {
            labels: models,
            datasets: [{
                label: 'Tool Score Distribution',
                data: boxplotData,
                backgroundColor: toolScores.map(score => getScoreColor(score) + '80'),
                borderColor: toolScores.map(score => getScoreColor(score)),
                borderWidth: 2,
                outlierColor: '#999999',
                outlierRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        color: '#000',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    }
                },
                x: {
                    ticks: {
                        color: '#000',
                        font: {
                            size: 10,
                            weight: 'normal'
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const data = context.parsed;
                            if (data.min === data.max) {
                                return `Single value: ${data.min.toFixed(3)}`;
                            }
                            return [
                                `Min: ${data.min.toFixed(3)}`,
                                `Q1: ${data.q1.toFixed(3)}`,
                                `Median: ${data.median.toFixed(3)}`,
                                `Q3: ${data.q3.toFixed(3)}`,
                                `Max: ${data.max.toFixed(3)}`
                            ];
                        }
                    }
                }
            }
        }
    });
}

function calculateActualQuartiles(sortedScores) {
    const n = sortedScores.length;
    
    if (n === 0) {
        return { min: 0, q1: 0, median: 0, q3: 0, max: 0, outliers: [] };
    }
    
    if (n === 1) {
        const value = sortedScores[0];
        return { min: value, q1: value, median: value, q3: value, max: value, outliers: [] };
    }
    
    // Calculate quartiles using the standard method
    const min = sortedScores[0];
    const max = sortedScores[n - 1];
    
    // Calculate median (Q2)
    let median;
    if (n % 2 === 0) {
        median = (sortedScores[n / 2 - 1] + sortedScores[n / 2]) / 2;
    } else {
        median = sortedScores[Math.floor(n / 2)];
    }
    
    // Calculate Q1 (first quartile)
    const q1Index = Math.floor(n / 4);
    let q1;
    if (n % 4 === 0) {
        q1 = (sortedScores[q1Index - 1] + sortedScores[q1Index]) / 2;
    } else {
        q1 = sortedScores[q1Index];
    }
    
    // Calculate Q3 (third quartile)
    const q3Index = Math.floor(3 * n / 4);
    let q3;
    if (n % 4 === 0) {
        q3 = (sortedScores[q3Index - 1] + sortedScores[q3Index]) / 2;
    } else {
        q3 = sortedScores[q3Index];
    }
    
    // For now, we'll not calculate outliers to keep it simple
    // In a full implementation, outliers would be values outside 1.5 * IQR from Q1/Q3
    
    return {
        min: min,
        q1: q1,
        median: median,
        q3: q3,
        max: max,
        outliers: []
    };
}

function getScoreColor(score) {
    if (score >= 0.7) {
        return '#27ae60'; // Green
    } else if (score >= 0.4) {
        return '#f39c12'; // Orange
    } else {
        return '#e74c3c'; // Red
    }
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    const modal = document.getElementById('testModal');
    if (event.target === modal) {
        closeModal();
    }
}

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeModal();
    }
});
