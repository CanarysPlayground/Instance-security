/**
 * @name Hard-coded credentials
 * @description Detects hard-coded API keys, secrets, or tokens in string literals.
 * @kind problem
 * @problem.severity warning
 * @id java/hardcoded-credentials
 * @tags security
 */

import java

from StringLiteral s
where s.getValue().regexpMatch(".*(api_key|secret|token|password)=[a-zA-Z0-9]+.*")
select s, "Potential hard-coded credential detected: " + s.getValue()
