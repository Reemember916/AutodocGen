document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Reveal Animations
    const revealElements = document.querySelectorAll('.reveal');

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                // Optional: stop observing once revealed
                // revealObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: "0px 0px -50px 0px" // Start reveal slightly before entering
    });

    revealElements.forEach((el, index) => {
        // Optional: add slight delay based on order if they are grid items
        if (el.classList.contains('grid-item')) {
            el.style.transitionDelay = `${(index % 3) * 0.15}s`;
        }
        revealObserver.observe(el);
    });

    // 2. Navbar Scroll Effect
    const nav = document.querySelector('nav div.glass');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 20) {
            nav.classList.add('py-2');
            nav.classList.remove('py-3');
            nav.classList.add('shadow-xl', 'bg-slate-950/80');
        } else {
            nav.classList.add('py-3');
            nav.classList.remove('py-2');
            nav.classList.remove('shadow-xl', 'bg-slate-950/80');
        }
    });

    // 3. Smooth Scroll for Anchor Links (Native handled by class="scroll-smooth" on html, 
    // but this ensures it works across all links including buttons)
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            e.preventDefault();
            const targetElement = document.querySelector(targetId);

            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 100, // Offset for fixed nav
                    behavior: 'smooth'
                });
            }
        });
    });

    // 4. Parallax Hero Visual
    const heroImage = document.querySelector('.hero-visual img');
    if (heroImage) {
        window.addEventListener('scroll', () => {
            const speed = 0.05;
            const rect = heroImage.getBoundingClientRect();
            if (rect.top < window.innerHeight && rect.bottom > 0) {
                const yPos = (window.scrollY * speed);
                heroImage.style.transform = `translateY(${yPos}px) scale(1.02)`;
            }
        });
    }

    // 5. Cursor Feedback (Subtle interaction)
    const glassCards = document.querySelectorAll('.glass');
    glassCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            // Set CSS variables for spotlight effect if needed
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });

    // 6. I18n Support (English and Chinese)
    const translations = {
        'en': {
            'nav-features': 'Features',
            'nav-workflow': 'Workflow',
            'nav-star': 'Star Project',
            'hero-tag': 'v1.2.0 is out now',
            'hero-title': 'Structural <span class="bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Word Diff</span> for High-Stakes Docs',
            'hero-desc': 'Stop missing critical changes in massive technical specifications. DocDiff uses AST parsing to understand hierarchy, ensuring 100% accurate "Change Order" generation.',
            'btn-start': 'Get Started',
            'btn-source': 'View Source',
            'features-title': 'The New Standard for Document Review',
            'features-desc': 'DocDiff replaces manual eyes and basic line diffs with a sophisticated structural analysis engine.',
            'f1-title': 'AST-Based Parsing',
            'f1-desc': 'We don\'t just compare text. We build an Abstract Syntax Tree of your .docx, preserving the relationship between headings (H1-H4) and content.',
            'f2-title': 'Stable Section ID\'s',
            'f2-desc': 'Detects stable ID\'s in headings (like D/R_SDD01_...) to match sections even if titles are renamed or moved.',
            'f3-title': 'Deep Table Diffing',
            'f3-desc': 'Drills into table rows to identify exact changes, additions, or deletions while maintaining table header context.',
            'how-title': 'From Raw Documents to <span class="text-primary italic">Professional</span> Results',
            'how-title-accent': 'Professional',
            'step1-title': 'Ingest DOCX',
            'step1-desc': 'Upload or point the CLI to your original and revised Word documents.',
            'step2-title': 'Normalize & Match',
            'step2-desc': 'DocDiff uses smart heuristics to align chapters, sections, and paragraphs.',
            'step3-title': 'Generate Change Order',
            'step3-desc': 'A perfectly formatted .docx is generated, ready for formal submission or internal review.',
            'cta-title': 'Secure your technical workflow today.',
            'cta-desc': 'Open source, Python-powered, and built for structural precision.',
            'cta-btn': 'Get Started Free'
        },
        'zh': {
            'nav-features': '功能特性',
            'nav-workflow': '工作流程',
            'nav-star': '项目收藏',
            'hero-tag': 'v1.2.0 现已发布',
            'hero-title': '结构化 <span class="bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Word 对比</span>，专为高标准文档设计',
            'hero-desc': '别再错过海量技术规范中的关键修改。DocDiff 利用 AST 解析理解层级，确保 100% 准确生成“文档更改说明书”。',
            'btn-start': '立即开始',
            'btn-source': '查看源码',
            'features-title': '文档审查的新标准',
            'features-desc': 'DocDiff 以先进的结构分析引擎取代人工肉眼和基础行对比。',
            'f1-title': '基于 AST 的层级解析',
            'f1-desc': '我们不仅仅对比文本。通过构建 .docx 的抽象语法树，我们精确保留标题（H1-H4）与内容之间的结构化联系。',
            'f2-title': '稳定的章节 ID 匹配',
            'f2-desc': '自动识别标题中的稳定编号（如 D/R_SDD01_...），即使标题名称变更或位置移动也能实现跨版本对齐。',
            'f3-title': '深度表格差异识别',
            'f3-desc': '深入表格行级颗粒度，在保留表头上下文的同时，精确识别单元格内容的增删改情况。',
            'how-title': '从原始文档到 <span class="text-primary italic">专业级别</span> 的变更产物',
            'how-title-accent': '专业级别',
            'step1-title': '导入文档',
            'step1-desc': '直接上传或将 CLI 工具指向您的原始 PDF/Word 以及修订后的版本。',
            'step2-title': '标准化对齐',
            'step2-desc': 'DocDiff 运用智能启发式算法，自动对齐跨版本的章节、段落及表格内容。',
            'step3-title': '生成更改单',
            'step3-desc': '自动生成格式完美的“文档修订说明书”，可直接用于正式提交或内部质量评审。',
            'cta-title': '立即升级您的技术文档流程。',
            'cta-desc': '开源授权、Python 驱动，专为追求结构化精度的极客而生。',
            'cta-btn': '免费开始使用'
        }
    };

    let currentLang = localStorage.getItem('docdiff-lang') || 'en';

    function updateLanguage(lang) {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (translations[lang] && translations[lang][key]) {
                el.innerHTML = translations[lang][key];
            }
        });
        document.documentElement.lang = lang;
        localStorage.setItem('docdiff-lang', lang);

        // Update language toggle text highlight
        const toggleBtn = document.getElementById('lang-toggle');
        if (toggleBtn) {
            toggleBtn.innerHTML = lang === 'en' ? 'EN / <span class="opacity-50 text-slate-500">中文</span>' : '<span class="opacity-50 text-slate-500">EN</span> / 中文';
        }
    }

    // Initialize language
    updateLanguage(currentLang);

    // Toggle event
    const langToggleTrigger = document.getElementById('lang-toggle');
    if (langToggleTrigger) {
        langToggleTrigger.addEventListener('click', () => {
            currentLang = currentLang === 'en' ? 'zh' : 'en';
            updateLanguage(currentLang);
        });
    }
});
