import multiprocessing
import shutil
import warnings

import numpy as np
import sklearn.datasets
import sklearn.metrics
import sklearn.model_selection
from autosklearn.classification import AutoSklearnClassifier
from autosklearn.constants import *
from autosklearn.metrics import accuracy
from smac.facade.roar_facade import ROAR
from smac.scenario.scenario import Scenario

from benchmark import OpenMLBenchmark

timeout = 3600
run_timeout = 360
jobs = 8
random = False

ensemble_size = 20


def get_random_search_object_callback(scenario_dict, seed, ta, backend, metalearning_configurations, runhistory):
    """Random search."""
    scenario_dict['input_psmac_dirs'] = backend.get_smac_output_glob()
    scenario_dict['minR'] = len(scenario_dict['instances'])
    scenario_dict['initial_incumbent'] = 'RANDOM'
    scenario = Scenario(scenario_dict)
    return ROAR(
        scenario=scenario,
        rng=seed,
        tae_runner=ta,
        runhistory=runhistory,
        run_id=seed
    )


def get_spawn_classifier(X_train, y_train, tmp_folder, output_folder):
    def spawn_classifier(seed, dataset_name):
        # Use the initial configurations from meta-learning only in one out of
        # the processes spawned. This prevents auto-sklearn from evaluating the
        # same configurations in all processes.
        if seed == 0:
            initial_configurations_via_metalearning = 25
            smac_scenario_args = {}
        else:
            initial_configurations_via_metalearning = 0
            smac_scenario_args = {'initial_incumbent': 'RANDOM'}

        callback = None
        if random:
            callback = get_random_search_object_callback

        # Arguments which are different to other runs of auto-sklearn:
        # 1. all classifiers write to the same output directory
        # 2. shared_mode is set to True, this enables sharing of data between
        # models.
        # 3. all instances of the AutoSklearnClassifier must have a different seed!
        automl = AutoSklearnClassifier(
            time_left_for_this_task=timeout,
            per_run_time_limit=run_timeout,
            shared_mode=True,
            tmp_folder=tmp_folder,
            output_folder=output_folder,
            delete_tmp_folder_after_terminate=False,
            ensemble_size=0,
            initial_configurations_via_metalearning=initial_configurations_via_metalearning,
            seed=seed,
            smac_scenario_args=smac_scenario_args,
            get_smac_object_callback=callback
        )
        automl.fit(X_train, y_train, dataset_name=dataset_name)
        print(automl.sprint_statistics())

    return spawn_classifier


def main(bm: OpenMLBenchmark):
    name = bm.get_meta_information()['name']

    X_train = np.concatenate((bm.X_valid, bm.X_train))
    y_train = np.concatenate((bm.y_valid, bm.y_train))
    X_test = bm.X_test
    y_test = bm.y_test

    tmp_folder = '/tmp/autosklearn/{}/tmp'.format(name)
    output_folder = '/tmp/autosklearn/{}/out'.format(name)

    processes = []
    spawn_classifier = get_spawn_classifier(X_train, y_train, tmp_folder, output_folder)
    for i in range(jobs):
        p = multiprocessing.Process(target=spawn_classifier, args=(i, name))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

    print('Starting to build an ensemble!')
    automl = AutoSklearnClassifier(
        time_left_for_this_task=3600,
        per_run_time_limit=run_timeout,
        shared_mode=True,
        ensemble_size=ensemble_size,
        tmp_folder=tmp_folder,
        output_folder=output_folder,
        initial_configurations_via_metalearning=0,
        seed=1,
    )
    automl.fit_ensemble(
        y_train,
        task=MULTICLASS_CLASSIFICATION,
        metric=accuracy,
        precision='32',
        dataset_name='digits',
        ensemble_size=ensemble_size
    )

    predictions = automl.predict(X_test)
    print(automl.show_models())
    print('Misclassification rate', 1 - sklearn.metrics.accuracy_score(y_test, predictions))


if __name__ == '__main__':
    try:
        shutil.rmtree('tmp/autosklearn/')
    except OSError as e:
        pass

    print('Timeout: ', timeout)
    print('Run Timeout: ', run_timeout)
    print('Random Search: ', random)

    task_ids = [22, 37, 2079, 3543, 3899, 3913, 3917, 9950, 9980, 14966]
    for task in task_ids:
        print('Starting task {}'.format(task))
        bm = OpenMLBenchmark(task)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            main(bm)