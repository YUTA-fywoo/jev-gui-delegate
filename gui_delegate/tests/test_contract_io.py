import asyncio,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from jsonschema import Draft202012Validator
from gui_delegate.contract_io import load,input_schema
from gui_delegate.schema import Contract
from gui_delegate.security import Stop
from gui_delegate.examples import workflow

class ContractIOTests(unittest.TestCase):
    def test_compact_schema_preserves_all_inline_fields(self):
        schema=input_schema();value=workflow()
        Draft202012Validator(schema).validate(value)
        self.assertEqual(set(schema['properties']),set(Contract.model_json_schema()['properties'])|{'contract_path'})
        self.assertLess(len(json.dumps(schema)),2000)
        self.assertEqual(Contract.model_validate(load(value)),Contract.model_validate(value))
    def test_file_and_inline_contracts_are_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'contract.json';p.write_text(json.dumps(workflow(),ensure_ascii=False),'utf-8')
            args={'contract_path':str(p)};Draft202012Validator(input_schema()).validate(args)
            self.assertEqual(Contract.model_validate(load(args)),Contract.model_validate(workflow()))
    def test_mixed_envelope_cannot_override_scope(self):
        with self.assertRaisesRegex(Stop,'CONTRACT_ENVELOPE_MIXED'):load({'contract_path':'C:/fake.json','scope':{}})
    def test_network_ads_relative_wrong_suffix_denied(self):
        for path in ['relative.json',r'\\server\share\contract.json','C:/file.json:stream.json','C:/file.txt',123]:
            with self.subTest(path=path),self.assertRaisesRegex(Stop,'CONTRACT_PATH_DENIED'):load({'contract_path':path})
    def test_large_invalid_and_nonobject_files_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'contract.json'
            for content,error in [('x'*1_000_001,'CONTRACT_TOO_LARGE'),('not JSON','CONTRACT_FILE_INVALID'),('[]','INVALID_TASK_SCHEMA')]:
                p.write_text(content,'utf-8')
                with self.assertRaisesRegex(Stop,error):load({'contract_path':str(p)})
    def test_missing_file_error_does_not_disclose_contents(self):
        with self.assertRaisesRegex(Stop,'CONTRACT_FILE_INVALID'):load({'contract_path':'C:/unavailable-synthetic-contract.json'})
    def test_reparse_path_rejected(self):
        with patch.object(Path,'lstat',return_value=SimpleNamespace(st_file_attributes=0x400)),patch.object(Path,'is_symlink',return_value=False):
            with self.assertRaisesRegex(Stop,'CONTRACT_LINK_DENIED'):load({'contract_path':'C:/synthetic.json'})
    def test_opaque_nested_objects_still_strictly_validated_before_spawn(self):
        from gui_delegate import service
        from pydantic import ValidationError
        with tempfile.TemporaryDirectory() as directory,patch.object(service.subprocess,'Popen') as spawn:
            p=Path(directory)/'contract.json';value=workflow();value['steps'][0]['arbitrary_code']='forbidden'
            p.write_text(json.dumps(value),'utf-8')
            with self.assertRaises(ValidationError):asyncio.run(service.run_task({'contract_path':str(p)}))
            spawn.assert_not_called()
    def test_scope_still_rejected_before_spawn(self):
        from gui_delegate import service
        with tempfile.TemporaryDirectory() as directory,patch.object(service.subprocess,'Popen') as spawn:
            p=Path(directory)/'contract.json';value=workflow();value['scope']['origins']=[]
            p.write_text(json.dumps(value),'utf-8')
            with self.assertRaisesRegex(Stop,'ORIGIN_DENIED'):asyncio.run(service.run_task({'contract_path':str(p)}))
            spawn.assert_not_called()

if __name__=='__main__':unittest.main()
