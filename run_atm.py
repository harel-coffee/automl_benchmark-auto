import os
import shutil
import subprocess

import numpy as np
import pandas as pd

from benchmark import OpenMLBenchmark

timeout = 3600
run_timeout = 360
jobs = 4


def main(bm: OpenMLBenchmark):
    X_train = bm.X_train
    y_train = bm.y_train
    X_test = bm.X_test
    y_test = bm.y_test

    headers = bm.column_names + ['class']
    train = np.c_[X_train, y_train]
    test = np.c_[X_test, y_test]

    os.mkdir('/tmp/atm/{}'.format(bm.task_id))
    train_path = '/tmp/atm/{}/train.csv'.format(bm.task_id)
    test_path = '/tmp/atm/{}/test.csv'.format(bm.task_id)
    pd.DataFrame(train, columns=headers).to_csv(train_path, index=None)
    pd.DataFrame(test, columns=headers).to_csv(test_path, index=None)

    sql_path = '{}/assets/atm_sql.yaml'.format(os.getcwd())
    cmd = 'cd /vagrant/phd/exisiting_solutions/meta_frameworks/ATM/ && ' \
          'python3 scripts/enter_data.py --sql-config {sql} --run-config {cwd}/assets/atm_run.yaml ' \
          '--train-path {train_path} --test-path {test_path}' \
        .format(sql=sql_path, cwd=os.getcwd(), train_path=train_path, test_path=test_path)
    subprocess.call(cmd, shell=True)

    cmd = 'cd /vagrant/phd/exisiting_solutions/meta_frameworks/ATM/ && python3 scripts/worker.py --sql-config {}' \
        .format(sql_path)

    procs = [subprocess.Popen(cmd, shell=True) for i in range(jobs)]
    for p in procs:
        p.wait()

    subprocess.call(cmd, shell=True)


if __name__ == '__main__':
    for i in range(4):
        print('#######\nIteration {}\n#######'.format(i))

        try:
            shutil.rmtree('/tmp/atm/')
        except OSError as e:
            pass
        os.mkdir('/tmp/atm/')

        print('Timeout: ', timeout)
        print('Run Timeout: ', run_timeout)

        task_ids = [15, 23, 29, 3021, 41, 2079, 3560, 3561, 3904, 3946, 9955, 9985, 7592, 14969, 146606]
        for task in task_ids:
            print('Starting task {}'.format(task))
            bm = OpenMLBenchmark(task)

            main(bm)