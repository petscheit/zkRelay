import json
import subprocess
import sys
import toml
from pytest_httpserver import HTTPServer
from preprocessing.create_input import generateZokratesInputFromBlock
from preprocessing.create_input import generateZokratesInputForMerkleProof

def setup_test_environment(batch_size, batch_no, verbose=False):
    # rm output files from earlier tests
    subprocess.run(['rm', 'output/witness{}'.format(batch_no)], check=False)

    # check if correct files are already generated and zkRelay setup executed
    zkRelayConf = toml.load('./conf/zkRelay-cli.toml')
    if zkRelayConf['zokrates_file_generator']['batch_size'] is not batch_size:
        print('\nSetting up test environment...\n')
        subprocess.run(['zkRelay', '-v', str(verbose), 'generate-files', str(batch_size)],
                    check=True)
        subprocess.run(['zkRelay', '-v', str(verbose), 'setup'],
                    check=True)
        print('\nDone.')

"""
This function assumes that the cmd 'zkRelay validate' will execute 
the following function from the file 'preprocessing/zokrates_helper.py':

def validateBatchFromBlockNo(ctx, blockNo, batch_size):
    result = generateZokratesInputFromBlock(ctx, (blockNo-1)*batch_size+1, batch_size)
    os.system(cmd_compute_witness + result)
    os.system(cmd_generate_proof)
    os.system('mv witness output/witness' + str(blockNo))
    os.system('mv proof.json output/proof' + str(blockNo) + '.json')
"""
def exec_validate(ctx, conf_file_path, batch_size, batch_no, verbose=False):
        host = ctx.obj.get('bitcoin_client').get('host')
        port = ctx.obj.get('bitcoin_client').get('port')
        verbose_output = subprocess.DEVNULL if not verbose else subprocess.STDOUT

        # get json config for test case
        fd = open(
            './tests/test_data{}'.format(conf_file_path))
        config = json.load(fd)
        fd.close()

        try:
            with HTTPServer(host=host, port=port) as httpserver:
                # setup http server expected requests and responses
                request_count = len(config.get('http_responses'))
                for curr_request in range(request_count):
                    # expected_request_data = json.dumps(config.get('http_requests')[curr_request])\
                    #             if config.get('http_requests') is not None and not [] else None
                    expected_request_data = None
                    httpserver.expect_ordered_request(uri='/', data=expected_request_data)\
                                .respond_with_json(config.get('http_responses')[curr_request])

                # execute compute witness command from zokrates
                # SEE THE NOTE AT TOP OF THE FUNCITON FOR ASSUMPTIONS
                result = generateZokratesInputFromBlock(ctx, (batch_no-1)*batch_size+1, batch_size)

                try:
                    command_list = ('zokrates compute-witness --light -a ' + result).split(' ')
                    subprocess.run(command_list, stdout=verbose_output, check=True)
                    command_list = ('mv witness output/witness' + str(batch_no)).split(' ')
                    subprocess.run(command_list, stdout=verbose_output, check=True)
                except subprocess.CalledProcessError:
                    return False
        except:
            print('There was probably a problem with the http server.')
            print(sys.exc_info())
            httpserver.check_assertions()