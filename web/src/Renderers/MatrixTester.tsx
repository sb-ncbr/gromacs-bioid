import { JsonSchema, RankedTester, UISchemaElement, TesterContext, isObjectArrayWithNesting } from '@jsonforms/core';

const MatrixTester: RankedTester = (uischema: UISchemaElement, schema: JsonSchema, context: TesterContext) => {
        if (isObjectArrayWithNesting(uischema, schema, context)) {
            return 69;
        }
        return -1;
    };
  
export default MatrixTester;
