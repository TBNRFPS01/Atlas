from services.task_queue import TaskQueue


def test_priority_and_persistence(tmp_path):
    path = tmp_path / 'queue.json'
    queue = TaskQueue(path)
    low = queue.add('low', priority=1)
    high = queue.add('high', priority=10)
    assert queue.next().id == high.id
    assert queue.mark(high.id, 'running')
    assert TaskQueue(path).next().id == low.id
