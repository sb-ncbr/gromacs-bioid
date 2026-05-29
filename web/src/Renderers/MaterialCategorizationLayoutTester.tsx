import { JsonSchema, RankedTester, UISchemaElement, TesterContext, isCategorization, hasCategory } from '@jsonforms/core';

const MaterialCategorizationLayoutTester: RankedTester = (uischema: UISchemaElement, schema: JsonSchema, context: TesterContext) => {
    console.log("MaterialCategorizationLayoutTester", uischema, schema, context);
        if (isCategorization(uischema) && hasCategory(uischema)) {
            console.log("MaterialCategorizationLayoutTester: isCategorization");
            return 10;
        }
        console.log("MaterialCategorizationLayoutTester: isNOTCategorization");
        return -10;
    };
  
export default MaterialCategorizationLayoutTester;
