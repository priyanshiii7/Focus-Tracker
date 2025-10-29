        let dayChart, weekChart, monthChart;
        let currentUserName = 'Priyanshi';
        let currentTab = 'day';
        
        async function loadProfile() {
            const urlParams = new URLSearchParams(window.location.search);
            const userName = urlParams.get('name') || 'Priyanshi';
            currentUserName = userName;
            
            try {
                const response = await fetch(`/user/profile?name=${userName}`);
                const data = await response.json();
                
                // Apply theme
                document.body.className = data.background_theme || 'gradient-purple';
                document.querySelectorAll('.theme-option').forEach(opt => {
                    opt.classList.remove('active');
                    if (opt.classList.contains(data.background_theme)) {
                        opt.classList.add('active');
                    }
                });
                
                // Update profile info
                document.getElementById('profileName').textContent = data.user_name;
                document.getElementById('joinedDate').textContent = new Date(data.joined_date).toLocaleDateString();
                
                // Update profile picture
                const avatar = document.getElementById('profileAvatar');
                const initial = document.getElementById('profileInitial');
                if (data.profile_picture) {
                    initial.style.display = 'none';
                    const img = document.createElement('img');
                    img.src = data.profile_picture;
                    img.alt = data.user_name;
                    avatar.appendChild(img);
                } else {
                    initial.textContent = data.user_name.charAt(0).toUpperCase();
                    initial.style.display = 'block';
                }
                
                // Update stats
                document.getElementById('totalSessions').textContent = data.stats.total_sessions;
                document.getElementById('totalHours').textContent = data.stats.total_study_hours + 'h';
                document.getElementById('avgFocus').textContent = data.stats.average_focus_score + '%';
                document.getElementById('currentStreak').textContent = data.stats.current_streak;
                document.getElementById('longestSession').textContent = formatTime(data.stats.longest_session);
                document.getElementById('totalAlerts').textContent = data.stats.total_alerts;
                
                // Load analytics for current tab
                loadAnalytics('day');
                
            } catch (error) {
                console.error('Error loading profile:', error);
            }
        }
        
        async function uploadProfilePicture() {
            const fileInput = document.getElementById('fileUpload');
            const file = fileInput.files[0];
            
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('user_name', currentUserName);
            
            try {
                const response = await fetch('/user/profile/picture', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Update avatar display
                    const avatar = document.getElementById('profileAvatar');
                    const initial = document.getElementById('profileInitial');
                    initial.style.display = 'none';
                    
                    // Remove any existing image
                    const existingImg = avatar.querySelector('img');
                    if (existingImg) {
                        existingImg.remove();
                    }
                    
                    const img = document.createElement('img');
                    img.src = data.url;
                    img.alt = currentUserName;
                    avatar.appendChild(img);
                    
                    alert('Profile picture updated!');
                }
            } catch (error) {
                console.error('Error uploading picture:', error);
                alert('Failed to upload picture');
            }
        }
        
        async function changeTheme(theme) {
            document.body.className = theme;
            
            document.querySelectorAll('.theme-option').forEach(opt => {
                opt.classList.remove('active');
                if (opt.classList.contains(theme)) {
                    opt.classList.add('active');
                }
            });
            
            try {
                await fetch('/user/profile', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_name: currentUserName,
                        background_theme: theme
                    })
                });
            } catch (error) {
                console.error('Error updating theme:', error);
            }
        }
        
        function switchTab(tab, event) {
            currentTab = tab;
            
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
            document.getElementById(tab + 'Tab').classList.remove('hidden');
            
            loadAnalytics(tab);
        }
        
        async function loadAnalytics(period) {
            try {
                const response = await fetch(`/analytics/${period}?name=${currentUserName}`);
                const data = await response.json();
                const analytics = data.analytics;
                
                const prefix = period;
                document.getElementById(prefix + 'StudyTime').textContent = analytics.total_studying_hours + 'h';
                document.getElementById(prefix + 'Sessions').textContent = analytics.total_sessions;
                document.getElementById(prefix + 'FocusScore').textContent = analytics.focus_score + '%';
                
                if (period === 'day') {
                    document.getElementById('dayAlerts').textContent = analytics.total_alerts;
                    renderDayChart(analytics.daily_breakdown);
                } else if (period === 'week') {
                    document.getElementById('weekAvg').textContent = 
                        (analytics.total_studying_hours / 7).toFixed(1) + 'h';
                    renderWeekChart(analytics.daily_breakdown);
                    renderHeatmap('weekHeatmap', analytics.daily_breakdown, 7);
                } else if (period === 'month') {
                    const dailyData = analytics.daily_breakdown;
                    let bestDay = '-';
                    let maxTime = 0;
                    for (const [day, data] of Object.entries(dailyData)) {
                        if (data.studying > maxTime) {
                            maxTime = data.studying;
                            bestDay = new Date(day).toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric'});
                        }
                    }
                    document.getElementById('monthBestDay').textContent = bestDay;
                    renderMonthChart(analytics.daily_breakdown);
                    renderHeatmap('monthHeatmap', analytics.daily_breakdown, 30);
                }
                
            } catch (error) {
                console.error('Error loading analytics:', error);
            }
        }
        
        function renderDayChart(dailyData) {
            const ctx = document.getElementById('dayChart');
            if (!ctx) return;
            
            if (dayChart) dayChart.destroy();
            
            const today = new Date().toISOString().split('T')[0];
            const data = dailyData[today] || {studying: 0, distracted: 0, sessions: 0};
            
            const studyMinutes = (data.studying / 60).toFixed(0);
            const awayMinutes = (data.distracted / 60).toFixed(0);
            
            dayChart = new Chart(ctx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: ['Studying', 'Away/Distracted'],
                    datasets: [{
                        label: 'Time (minutes)',
                        data: [studyMinutes, awayMinutes],
                        backgroundColor: ['#48bb78', '#ed8936']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: `${data.sessions} sessions today`
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Minutes'
                            }
                        }
                    }
                }
            });
        }
        
        function renderWeekChart(dailyData) {
            const ctx = document.getElementById('weekChart');
            if (!ctx) return;
            
            if (weekChart) weekChart.destroy();
            
            const labels = [];
            const studyData = [];
            
            for (let i = 6; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                const dateKey = date.toISOString().split('T')[0];
                
                labels.push(date.toLocaleDateString('en-US', {weekday: 'short'}));
                const dayData = dailyData[dateKey] || {studying: 0};
                studyData.push((dayData.studying / 3600).toFixed(1));
            }
            
            weekChart = new Chart(ctx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Study Hours',
                        data: studyData,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        function renderMonthChart(dailyData) {
            const ctx = document.getElementById('monthChart');
            if (!ctx) return;
            
            if (monthChart) monthChart.destroy();
            
            const labels = [];
            const studyData = [];
            
            for (let i = 29; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                const dateKey = date.toISOString().split('T')[0];
                
                if (i % 3 === 0) {
                    labels.push(date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}));
                } else {
                    labels.push('');
                }
                
                const dayData = dailyData[dateKey] || {studying: 0};
                studyData.push((dayData.studying / 3600).toFixed(1));
            }
            
            monthChart = new Chart(ctx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Study Hours',
                        data: studyData,
                        backgroundColor: '#667eea'
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        function renderHeatmap(containerId, dailyData, days) {
            const container = document.getElementById(containerId);
            container.innerHTML = '';
            
            const today = new Date();
            for (let i = days - 1; i >= 0; i--) {
                const date = new Date(today);
                date.setDate(date.getDate() - i);
                const dateKey = date.toISOString().split('T')[0];
                
                const dayData = dailyData[dateKey];
                const hours = dayData ? (dayData.studying / 3600).toFixed(1) : 0;
                
                let level = 0;
                if (hours > 0) level = 1;
                if (hours > 1) level = 2;
                if (hours > 2) level = 3;
                if (hours > 3) level = 4;
                
                const box = document.createElement('div');
                box.className = `heatmap-day level-${level}`;
                box.setAttribute('data-tooltip', `${date.toLocaleDateString()}: ${hours}h`);
                container.appendChild(box);
            }
        }
        
        function formatTime(seconds) {
            if (!seconds || isNaN(seconds)) return '0:00';
            
            seconds = Math.floor(seconds);
            const hours = Math.floor(seconds / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}:${mins.toString().padStart(2, '0')}`;
            }
            return `${mins}:00`;
        }
        
        // Load profile on page load
        loadProfile();
