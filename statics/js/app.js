document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    const grid = document.getElementById('dashboard-grid');
    const statusIndicator = document.getElementById('connection-status');

    socket.on('connect', () => {
        console.log('Connected to server!');
        statusIndicator.className = 'connected';
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server!');
        statusIndicator.className = 'disconnected';
    });

    socket.on('market_data_update', (data) => {
        updateStockCard(data);
    });

    function updateStockCard(data) {
        let card = document.getElementById(data.symbol);

        if (!card) {
            card = document.createElement('div');
            card.className = 'stock-card';
            card.id = data.symbol;
            card.innerHTML = `
                <div class="card-header">
                    <div>
                        <div class="symbol">${data.symbol}</div>
                        <div class="ltp">0.00</div>
                    </div>
                    <div class="change">
                        <span class="change-arrow"></span>
                        <span>0.00%</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="indicator">
                        <div class="indicator-label">SMA (50)</div>
                        <div class="indicator-value sma">N/A</div>
                    </div>
                    <div class="indicator">
                        <div class="indicator-label">RSI (14)</div>
                        <div class="rsi-gauge">
                            <div class="gauge-bg"></div>
                            <div class="gauge-cover"></div>
                            <div class="gauge-needle"></div>
                        </div>
                        <div class="indicator-value rsi">N/A</div>
                    </div>
                </div>
                <div class="card-footer">
                    Last Volume: <span class="volume">0</span> | <span class="timestamp"></span>
                </div>
            `;
            grid.appendChild(card);
        }

        const ltpElement = card.querySelector('.ltp');
        const changeElement = card.querySelector('.change');
        const changeText = changeElement.querySelector('span:last-child');
        const changeArrow = changeElement.querySelector('.change-arrow');
        
        const oldLtp = parseFloat(ltpElement.textContent);
        if (oldLtp < data.ltp) {
            card.classList.remove('flash-down');
            card.classList.add('flash-up');
        } else if (oldLtp > data.ltp) {
            card.classList.remove('flash-up');
            card.classList.add('flash-down');
        }
        setTimeout(() => card.classList.remove('flash-up', 'flash-down'), 700);

        ltpElement.textContent = data.ltp.toFixed(2);
        changeText.textContent = `${data.percent_change.toFixed(2)}%`;

        if (data.percent_change > 0) {
            changeElement.className = 'change positive';
            changeArrow.textContent = '▲';
        } else if (data.percent_change < 0) {
            changeElement.className = 'change negative';
            changeArrow.textContent = '▼';
        } else {
            changeElement.className = 'change';
            changeArrow.textContent = '';
        }

        card.querySelector('.sma').textContent = data.sma !== null ? data.sma.toFixed(2) : 'N/A';
        card.querySelector('.rsi').textContent = data.rsi !== null ? data.rsi.toFixed(2) : 'N/A';
        card.querySelector('.volume').textContent = data.volume;
        card.querySelector('.timestamp').textContent = new Date(data.timestamp).toLocaleTimeString();
        
        // Update RSI Gauge Needle
        if (data.rsi !== null) {
            const needle = card.querySelector('.gauge-needle');
            const rotation = (Math.max(0, Math.min(100, data.rsi)) / 100) * 180 - 90;
            needle.style.transform = `rotate(${rotation}deg)`;
        }
    }
});