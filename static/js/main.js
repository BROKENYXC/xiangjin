// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('工业数据管理系统 - 页面已加载');
    
    // 为卡片添加点击效果
    const cards = document.querySelectorAll('.feature-card');
    
    cards.forEach(card => {
        card.addEventListener('click', function(e) {
            // 如果点击的不是按钮，则触发卡片的链接
            if (!e.target.classList.contains('btn')) {
                const link = this.querySelector('.btn');
                if (link) {
                    window.location.href = link.getAttribute('href');
                }
            }
        });
    });
}); 