# 前程无忧爬虫 - TDD设计方案 (Plan A)

## 目标
实现20000+数据规模的前程无忧爬虫，具备断点续传、批量控制和完整测试覆盖。

## 当前状态分析

### 已实现
- ✅ Job51Crawler类 (Selenium + 反检测)
- ✅ 22个字段完整映射
- ✅ 管理员界面 (crawl_admin.html)
- ✅ API端点 (crawl_start_api, crawl_status_api)
- ✅ Playwright测试框架 (12个测试, 8通过, 3失败)
- ✅ 基础去重 (title + companyTitle + address)
- ✅ CSV备份机制

### 存在的问题
1. **测试失败**:
   - `test_crawl_completion`: 60秒超时不够，前程无忧每页20-30秒
   - `test_real_time_updates`: 进度格式期望 `"/2"` 但实际返回 `"0/2"` 或 `"1/2"`
   - `test_status_api_returns_json`: API返回格式验证

2. **规模化缺失**:
   - 无断点续传 (checkpoint/resume)
   - 无批量控制 (batch processing)
   - 无状态持久化 (仅内存状态)
   - 无长时间运行容错

---

## TDD设计 - Phase 1: 测试修复

### Test 1: test_crawl_completion 修复
**问题**: 60秒超时对于前程无忧不够（每页20-30秒，1页也需要20-30秒）
**修复方案**:
- 延长超时到 120秒
- 或者使用 mock 方式测试完成流程

```python
# 修改测试代码
def test_crawl_completion(self, page: Page, login_as_admin):
    """测试爬虫完成流程 - 增加超时时间"""
    page.goto("http://localhost:8000/myApp/admin/crawl/")
    page.fill("#pages", "1")
    page.click("#startBtn")
    
    # 延长超时到120秒（前程无忧较慢）
    for i in range(24):  # 24 * 5 = 120秒
        page.wait_for_timeout(5000)
        status_text = page.locator("#crawlStatus").inner_text()
        if "已完成" in status_text or "error" in status_text.lower():
            break
```

### Test 2: test_real_time_updates 修复
**问题**: 进度格式检查需要等待爬虫实际推进
**修复方案**:
- 增加初始等待时间
- 检查格式为 `"0/2"` 或 `"1/2"` 或 `"2/2"` 均可

```python
# 修改断言
def test_real_time_updates(self, page: Page, login_as_admin):
    page.goto("http://localhost:8000/myApp/admin/crawl/")
    page.fill("#pages", "2")
    page.click("#startBtn")
    
    # 等待爬虫启动
    page.wait_for_timeout(3000)
    
    # 检查进度格式（可以是 0/2, 1/2, 或 2/2）
    current = page.locator("#currentPage").inner_text()
    assert any(f"{i}/2" in current for i in range(3)), f"进度格式错误: {current}"
```

### Test 3: test_status_api_returns_json 修复
**问题**: 需要确保API返回正确的JSON格式
**修复方案**: 检查views.py返回格式

```python
# views.py crawl_status_api 确保返回:
return JsonResponse({
    "status": _crawler_status["status"],
    "keyword": _crawler_status["keyword"],
    "city": _crawler_status["city"],
    "current_page": _crawler_status["current_page"],
    "total_pages": _crawler_status["total_pages"],
    "raw_count": _crawler_status["raw_count"],
    "saved_count": _crawler_status["saved_count"],
    "logs": status_copy["logs"],
})
```

---

## TDD设计 - Phase 2: 断点续传 (Checkpoint/Resume)

### 需求
爬虫崩溃或中断后，可以从断点继续，不重复爬取已完成的页面。

### 设计
1. **状态文件**: 使用JSON文件保存爬取进度
2. **保存时机**: 每完成一页保存一次
3. **恢复逻辑**: 启动时检查状态文件，跳过已完成页面

### 测试用例

```python
# tests/test_checkpoint.py

class TestCheckpointResume:
    """断点续传功能测试"""
    
    def test_save_checkpoint_after_page(self):
        """测试每页完成后保存检查点"""
        crawler = Job51Crawler()
        crawler.save_checkpoint(keyword="大数据", page=5, total_pages=10)
        
        assert os.path.exists("crawler_checkpoint.json")
        with open("crawler_checkpoint.json") as f:
            data = json.load(f)
        assert data["current_page"] == 5
        assert data["keyword"] == "大数据"
    
    def test_resume_from_checkpoint(self):
        """测试从检查点恢复"""
        # 创建模拟检查点
        checkpoint = {
            "keyword": "大数据",
            "city": "",
            "current_page": 5,
            "total_pages": 10,
            "completed_pages": [1, 2, 3, 4, 5],
            "timestamp": time.time()
        }
        with open("crawler_checkpoint.json", "w") as f:
            json.dump(checkpoint, f)
        
        crawler = Job51Crawler()
        resume_info = crawler.load_checkpoint()
        
        assert resume_info["current_page"] == 5
        assert resume_info["completed_pages"] == [1, 2, 3, 4, 5]
    
    def test_skip_completed_pages(self):
        """测试跳过已完成页面"""
        crawler = Job51Crawler()
        crawler.completed_pages = {1, 2, 3}
        
        # 应该跳过第1,2,3页，从第4页开始
        pages_to_crawl = crawler.get_remaining_pages(1, 5)
        assert pages_to_crawl == [4, 5]
    
    def test_clear_checkpoint_on_completion(self):
        """测试完成后清理检查点"""
        crawler = Job51Crawler()
        crawler.save_checkpoint(keyword="大数据", page=10, total_pages=10)
        crawler.clear_checkpoint()
        
        assert not os.path.exists("crawler_checkpoint.json")
```

### 实现代码

```python
# job51_crawler.py 新增方法

class Job51Crawler:
    def __init__(self):
        # ... 现有代码 ...
        self.checkpoint_file = "crawler_checkpoint.json"
        self.completed_pages = set()
    
    def save_checkpoint(self, keyword, city, page, total_pages):
        """保存检查点"""
        checkpoint = {
            "keyword": keyword,
            "city": city,
            "current_page": page,
            "total_pages": total_pages,
            "completed_pages": list(self.completed_pages),
            "timestamp": time.time()
        }
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False)
    
    def load_checkpoint(self):
        """加载检查点"""
        if not os.path.exists(self.checkpoint_file):
            return None
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.completed_pages = set(data.get("completed_pages", []))
                return data
        except Exception as e:
            print(f"加载检查点失败: {e}")
            return None
    
    def clear_checkpoint(self):
        """清除检查点"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        self.completed_pages = set()
    
    def get_remaining_pages(self, start_page, end_page):
        """获取剩余需要爬取的页面"""
        return [p for p in range(start_page, end_page + 1) 
                if p not in self.completed_pages]
```

---

## TDD设计 - Phase 3: 批量控制 (Batch Processing)

### 需求
将20000条数据分批处理，每批可控大小，支持批次间休息。

### 设计
1. **批次大小**: 每批50-100页（约1000-2000条数据）
2. **批次间隔**: 每批完成后休息5-10分钟
3. **批次状态**: 跟踪当前批次和总批次

### 测试用例

```python
# tests/test_batch_processing.py

class TestBatchProcessing:
    """批量控制功能测试"""
    
    def test_calculate_batch_count(self):
        """测试批次计算"""
        calculator = BatchCalculator(total_pages=100, batch_size=20)
        assert calculator.total_batches == 5
    
    def test_get_batch_range(self):
        """测试获取批次页面范围"""
        calculator = BatchCalculator(total_pages=100, batch_size=20)
        
        # 第1批: 1-20
        start, end = calculator.get_batch_range(1)
        assert start == 1 and end == 20
        
        # 第3批: 41-60
        start, end = calculator.get_batch_range(3)
        assert start == 41 and end == 60
    
    def test_batch_delay(self):
        """测试批次间延时"""
        processor = BatchProcessor(min_delay=300, max_delay=600)  # 5-10分钟
        delay = processor.get_batch_delay()
        assert 300 <= delay <= 600
    
    def test_save_batch_state(self):
        """测试保存批次状态"""
        processor = BatchProcessor()
        processor.save_batch_state(
            current_batch=2,
            completed_batches=[1],
            total_pages=100
        )
        
        assert os.path.exists("batch_state.json")
```

### 实现代码

```python
# batch_processor.py

class BatchCalculator:
    """批次计算器"""
    
    def __init__(self, total_pages, batch_size=50):
        self.total_pages = total_pages
        self.batch_size = batch_size
        self.total_batches = (total_pages + batch_size - 1) // batch_size
    
    def get_batch_range(self, batch_number):
        """获取指定批次的页面范围"""
        start = (batch_number - 1) * self.batch_size + 1
        end = min(batch_number * self.batch_size, self.total_pages)
        return start, end
    
    def get_progress(self, current_batch):
        """获取进度百分比"""
        return (current_batch / self.total_batches) * 100


class BatchProcessor:
    """批次处理器"""
    
    def __init__(self, min_delay=300, max_delay=600):
        self.min_delay = min_delay  # 秒
        self.max_delay = max_delay
        self.state_file = "batch_state.json"
    
    def get_batch_delay(self):
        """获取随机批次间隔"""
        return random.uniform(self.min_delay, self.max_delay)
    
    def save_batch_state(self, current_batch, completed_batches, total_pages):
        """保存批次状态"""
        state = {
            "current_batch": current_batch,
            "completed_batches": completed_batches,
            "total_pages": total_pages,
            "timestamp": time.time()
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f)
    
    def load_batch_state(self):
        """加载批次状态"""
        if not os.path.exists(self.state_file):
            return None
        with open(self.state_file, "r") as f:
            return json.load(f)
```

---

## TDD设计 - Phase 4: 大规模爬取20000+数据计划

### 计算
- 目标: 20000条数据
- 每页: ~20条
- 需要页数: 1000页
- 每页耗时: 22-30秒（含等待）
- 预估总时间: 1000 * 25秒 = 25000秒 ≈ 7小时（连续运行）
- 实际（含休息）: 10-12小时

### 分批策略
| 批次 | 页数范围 | 数据量 | 预估时间 | 休息 |
|------|----------|--------|----------|------|
| 1 | 1-100 | ~2000条 | 50分钟 | 10分钟 |
| 2 | 101-200 | ~2000条 | 50分钟 | 10分钟 |
| ... | ... | ... | ... | ... |
| 10 | 901-1000 | ~2000条 | 50分钟 | 完成 |

总计: 约10小时，20000条数据

### 反爬策略
1. **页面内延时**: 每页3-5秒随机
2. **页面间延时**: 4-7秒随机
3. **批次间休息**: 10-15分钟
4. **每5页额外休息**: 10-15秒
5. **User-Agent轮换**: 每50页换一个
6. **Cookie保持**: 登录后保持session

### 测试用例

```python
# tests/test_large_scale_crawl.py

class TestLargeScaleCrawl:
    """大规模爬取测试"""
    
    def test_estimate_crawl_time(self):
        """测试爬取时间估算"""
        estimator = CrawlEstimator(
            pages_per_batch=50,
            seconds_per_page=25,
            batch_rest_seconds=600
        )
        total_time = estimator.estimate_total_time(1000)
        # 1000页 = 20批, 每批约21分钟(50*25 + 600休息) = 约7小时
        assert 6 * 3600 <= total_time <= 8 * 3600
    
    def test_user_agent_rotation(self):
        """测试User-Agent轮换"""
        rotator = UserAgentRotator()
        agents = [rotator.get_agent() for _ in range(10)]
        # 应该有一定随机性
        assert len(set(agents)) > 1
    
    def test_rate_limiting(self):
        """测试速率限制"""
        limiter = RateLimiter(min_delay=3, max_delay=5)
        delays = [limiter.get_delay() for _ in range(10)]
        assert all(3 <= d <= 5 for d in delays)
```

---

## 实施计划

### Week 1: 测试修复 + 基础框架
- [ ] 修复3个Playwright测试
- [ ] 实现Checkpoint类
- [ ] 编写Checkpoint单元测试
- [ ] 集成Checkpoint到Job51Crawler

### Week 2: 批量控制
- [ ] 实现BatchCalculator
- [ ] 实现BatchProcessor
- [ ] 编写Batch单元测试
- [ ] 集成到run_crawler函数

### Week 3: 大规模爬取
- [ ] 实施20000数据爬取计划
- [ ] 实施反爬策略增强
- [ ] 监控和日志完善
- [ ] 数据验证

### Week 4: 文档和论文
- [ ] 编写实施文档
- [ ] 生成论文所需截图
- [ ] 数据分析
- [ ] 论文撰写

---

## 风险缓解

### 风险1: 前程无忧反爬加强
- **缓解**: 实施登录机制、代理轮换、更慢速率
- **备用**: 增加更多关键词分散爬取

### 风险2: 长时间运行崩溃
- **缓解**: 断点续传机制，每页保存进度
- **缓解**: 小批次运行，降低单次风险

### 风险3: 数据重复
- **缓解**: 数据库去重（title + company + address）
- **缓解**: 检查点记录已爬取页面

---

## 关键指标

- **数据质量**: >95%有效数据（非空字段>80%）
- **爬取速度**: 平均每小时1000-1500条
- **成功率**: >90%页面成功获取
- **断点恢复**: 100%可从任意页面恢复

